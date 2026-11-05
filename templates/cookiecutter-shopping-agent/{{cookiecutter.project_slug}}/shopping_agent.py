"""{{ cookiecutter.agent_name }} — shopping agent generated from the ProveCart Cookiecutter template (provider: {{ cookiecutter.provider }}{% if cookiecutter.use_mcp %}, MCP companion included as mcp_agent.py{% endif %}).

Original starter docstring: Shopping agent starter — OpenAI Agents SDK, with the
ProveCart conformity check wired BEFORE payment.

The pattern this starter teaches (copy it, keep it):

    customer instruction -> build cart -> CHECK -> MATCH: pay
                                              -> BLOCK: fix inside
                                                 the customer's
                                                 authorization and
                                                 re-check (linked)
                                              -> REVIEW: stop and
                                                 ask the customer

The payment tool refuses to run unless the most recent check in
this process returned MATCH. That refusal is the point of the
starter: the check is a structural step in the flow, not a
suggestion in a prompt.

Offline by default: with LIVE_MODE unset/false, the check tool
routes to a local mock with the same response shape, so the whole
loop runs with no keys at all. Set LIVE_MODE=true and
PROVECART_API_KEY to call the real ProveCart API (free signup for
an integrator key: https://provecart.com/agents.md).

Run the offline demo:   python shopping_agent.py
Run with the SDK loop:  python shopping_agent.py --sdk   (needs
                        OPENAI_API_KEY; LIVE_MODE decides check
                        target)
"""
import json
import os
import sys

LIVE_MODE = os.environ.get("LIVE_MODE", "false").lower() == "true"

# In-memory run state. A production agent should carry the check
# record_id in its own run/session state; the shape is what matters:
# payment is gated on the LAST check's verdict.
STATE = {"last_verdict": None, "last_record_id": None}


# ----------------------------------------------------------------
# The check — one implementation, two transports (mock / live).
# ----------------------------------------------------------------

def _mock_check(cart_changed, previous_record_id):
    """Local stand-in with the real response shape. First look at
    the demo cart returns BLOCK with a correctable fix; the linked
    resubmission returns MATCH."""
    if previous_record_id:
        return {"verdict": "MATCH", "record_id": "rec_mock_2",
                "corrections": [], "max_attempts": 3}
    return {"verdict": "BLOCK", "record_id": "rec_mock_1",
            "max_attempts": 3,
            "corrections": [{
                "code": "com.provecart.conformity.variant_mismatch",
                "severity": "recoverable",
                "path": "$.items[0].variant",
                "expected": "step-through", "actual": "step-over",
                "action": "change_variant",
                "requires_buyer_approval": False}]}


def run_check(mandate_id, merchant, items, total_price,
              previous_record_id=None):
    """Call the conformity check; remember the verdict for the
    payment gate."""
    if not LIVE_MODE:
        out = _mock_check(bool(previous_record_id), previous_record_id)
    else:
        from provecart_client import ProveCartClient
        client = ProveCartClient(os.environ["PROVECART_API_KEY"])
        out = client.verify_cart(mandate_id, merchant, items,
                                 total_price,
                                 previous_record_id=previous_record_id)
    STATE["last_verdict"] = out.get("verdict")
    STATE["last_record_id"] = out.get("record_id")
    return out


# ----------------------------------------------------------------
# Agents SDK wiring.
# ----------------------------------------------------------------

def build_agent():
    from agents import Agent, function_tool

    @function_tool
    def check_cart_before_payment(mandate_id: str, merchant_json: str,
                                  items_json: str, total_price: float,
                                  previous_record_id: str = "") -> str:
        """Check a built cart against the customer's signed
        instructions BEFORE capturing payment. On BLOCK, apply only
        fixes inside the customer's existing authorization and call
        again with previous_record_id set to the blocked check's
        record_id. On REVIEW, stop and ask the buyer."""
        out = run_check(mandate_id, json.loads(merchant_json),
                        json.loads(items_json), total_price,
                        previous_record_id or None)
        return json.dumps(out)

    @function_tool
    def capture_payment(amount: float, currency: str = "USD") -> str:
        """Capture payment. Refuses unless the most recent
        conformity check in this run returned MATCH."""
        if STATE["last_verdict"] != "MATCH":
            return json.dumps({
                "captured": False,
                "reason": ("no MATCH verdict in this run "
                           f"(last: {STATE['last_verdict']}); run "
                           "check_cart_before_payment first")})
        # A real integration calls its payment provider here, and
        # keeps STATE["last_record_id"] with the order as evidence.
        return json.dumps({"captured": True, "amount": amount,
                           "currency": currency,
                           "check_record_id": STATE["last_record_id"]})

    return Agent(
        name="{{ cookiecutter.agent_name }}",
        instructions=(
            "You buy on the customer's behalf. For every purchase: "
            "build the cart, call check_cart_before_payment, and "
            "only call capture_payment after a MATCH. On BLOCK, "
            "apply the corrections that stay inside the customer's "
            "instructions and re-check with previous_record_id. On "
            "REVIEW, stop and ask the customer — never guess."),
        tools=[check_cart_before_payment, capture_payment])


# ----------------------------------------------------------------
# Offline demo — the loop, with no SDK and no keys.
# ----------------------------------------------------------------

def demo():
    merchant = {"name": "TrailVolt", "domain": "trailvolt.example"}
    items = [{"name": "Spare battery", "variant": "step-over",
              "quantity": 1, "unit_price": 431.0,
              "category": "battery", "brand": "TrailVolt"}]
    total = 431.0

    print("1) check the built cart (wrong variant on purpose)")
    out = run_check("mandate_demo", merchant, items, total)
    print("   ->", out["verdict"], out.get("corrections"))

    print("2) apply the in-authorization fix and re-check, linked")
    items[0]["variant"] = "step-through"
    out = run_check("mandate_demo", merchant, items, total,
                    previous_record_id=out["record_id"])
    print("   ->", out["verdict"], "record", out["record_id"])

    print("3) payment gate: capture is allowed only now, after MATCH")
    print("   gate state:", STATE["last_verdict"],
          "-> capture would proceed, keeping record",
          STATE["last_record_id"], "with the order")
    print("   (run with --sdk for the full Agents SDK loop)")


if __name__ == "__main__":
    if "--sdk" in sys.argv:
        import asyncio
        from agents import Runner
        agent = build_agent()
        result = asyncio.run(Runner.run(
            agent,
            "Buy the spare battery for my step-through bike, "
            "under $450, from TrailVolt."))
        print(result.final_output)
    else:
        demo()
