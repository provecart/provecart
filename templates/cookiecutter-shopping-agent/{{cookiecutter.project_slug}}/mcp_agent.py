"""MCP shopping-agent starter — no framework, raw MCP client.

Connects to ProveCart's MCP server
(https://api.provecart.com/mcp) with the official MCP Python SDK
and walks the whole agent funnel with tool calls only:

    list tools -> read the public record -> sign up (keyless,
    the server issues a scoped exam key) -> start the live
    certification exam -> answer with this agent's own decisions
    -> receive score, permanent result URL, live badge

That loop is the starter's point: an agent built from this file
meets ProveCart at birth, through the protocol, with no human
signing it up and no pre-issued key. The same server carries the
pre-payment check tools (verify cart / booking / reservation);
in a purchase loop they slot in exactly where
shopping-agent-openai's check_cart_before_payment sits: after
building the order, before capturing payment.

Arguments are assembled from each tool's declared inputSchema at
runtime, so this file keeps working if optional fields change.

Run:  pip install -r requirements.txt && python mcp_agent.py
      python mcp_agent.py --name "My Agent"   (scoreboard name)
"""
import argparse
import asyncio
import json
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SERVER = "https://api.provecart.com/mcp"
SRC = "mcp-starter"


def tool_json(result):
    """Extract the JSON payload from a CallToolResult."""
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except Exception:
                return {"text": text}
    return {}


async def call(session, tools, name, **kwargs):
    """Call a tool, passing only the arguments its schema declares."""
    schema = tools[name].inputSchema or {}
    props = (schema.get("properties") or {})
    args = {k: v for k, v in kwargs.items() if k in props or not props}
    result = await session.call_tool(name, args)
    if getattr(result, "isError", False):
        raise RuntimeError(f"{name} -> {tool_json(result)}")
    return tool_json(result)


# ----------------------------------------------------------------
# DEMO POLICY — a placeholder with the right shape.
# The exam grades YOUR agent's decisions; replace decide() with
# your model. The shape to keep: choose only when the instruction
# settles the choice; otherwise ASK. Guessing is the failure the
# exam exists to catch.
# ----------------------------------------------------------------

def _options(task):
    for key in ("options", "candidates", "shelf", "items", "choices"):
        if isinstance(task.get(key), list):
            return task[key]
    return []


def _instruction(task):
    for key in ("instruction", "prompt", "customer_instruction", "text"):
        if isinstance(task.get(key), str):
            return task[key]
    return json.dumps(task)


def decide(task):
    """Return {"choice": <option id/index>} or {"ask": True}."""
    instruction = _instruction(task).lower()
    options = _options(task)
    if not options:
        return {"ask": True}

    ceiling = None
    m = re.search(r"under \$?([\d,]+(?:\.\d+)?)", instruction)
    if m:
        ceiling = float(m.group(1).replace(",", ""))

    def price(opt):
        for key in ("price", "total_price", "unit_price", "cost"):
            if isinstance(opt.get(key), (int, float)):
                return float(opt[key])
        return None

    def blob(opt):
        return json.dumps(opt).lower()

    # Required attribute tokens the instruction names explicitly
    # (e.g. "step-through", " refundable") must appear in the pick.
    required = [t for t in ("step-through", "step-over",
                            "refundable", "non-refundable",
                            "window", "aisle") if t in instruction]

    survivors = []
    for i, opt in enumerate(options):
        if ceiling is not None:
            p = price(opt)
            if p is None or p > ceiling:
                continue
        if any(t not in blob(opt) for t in required):
            continue
        survivors.append((i, opt))

    if len(survivors) == 1:
        i, opt = survivors[0]
        return {"choice": opt.get("id", i)}
    return {"ask": True}


async def main(agent_name):
    async with streamablehttp_client(SERVER) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listing = await session.list_tools()
            tools = {t.name: t for t in listing.tools}
            print("tools on the server:")
            for name in sorted(tools):
                print("  -", name)

            board = await call(session, tools,
                               "provecart_scoreboard")
            print("\npublic record (truncated):",
                  json.dumps(board)[:200])

            signup = await call(session, tools,
                                "provecart_agent_signup",
                                agent_name=agent_name, src=SRC)
            agent_id = signup.get("agent_id")
            api_key = signup.get("api_key") or signup.get("key")
            print("\nsigned up:", agent_id)

            start = await call(session, tools,
                               "provecart_agent_exam_start",
                               agent_id=agent_id, api_key=api_key)
            session_id = start.get("session_id") or start.get("id")
            tasks = start.get("tasks") or []
            print(f"exam started: {len(tasks)} tasks")

            decisions = {}
            for task in tasks:
                tid = task.get("task_id") or task.get("id")
                decisions[tid] = decide(task)
            graded = await call(session, tools,
                                "provecart_agent_exam_answer",
                                session_id=session_id,
                                agent_id=agent_id, api_key=api_key,
                                answers=decisions, decisions=decisions)
            print("\ngraded:", json.dumps(graded, indent=2)[:800])
            print("\nThe answer response carries the permanent "
                  "result URL and, on a pass, the signed "
                  "credential — carry them in your agent's card "
                  "and final reports; they are how stores and "
                  "other agents verify the claim.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="MCP Starter Agent")
    asyncio.run(main(ap.parse_args().name))
