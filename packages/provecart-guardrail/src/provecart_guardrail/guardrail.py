
"""OpenAI Agents SDK guardrail that checks BEFORE a purchase tool runs.

Semantics (GuardrailFunctionOutput: ``output_info`` + ``tripwire_triggered``):

  MATCH                       -> tripwire False, proceed.
  REVIEW                      -> tripwire True, escalate to the buyer.
  BLOCK, no usable correction -> tripwire True, escalate.
  BLOCK, known corrections    -> corrections always land in
      ``output_info``. Tripwire depends on ONE explicit choice:
      ``auto_fix=False`` (default) trips the wire, so a human / outer
      loop decides; ``auto_fix=True`` does NOT trip, and ``output_info``
      carries ``routing="fix"`` plus the corrections and
      ``record_id`` so the caller's correction loop can apply ONLY
      repairs inside the existing authorization and re-check with
      ``previous_record_id``. Pick ``auto_fix=True`` only if that loop
      actually exists — otherwise the guardrail fails open in spirit.

If the OpenAI Agents SDK is installed, the real
``agents.GuardrailFunctionOutput`` is returned. Otherwise a local
dataclass with the same two fields is used, so the package imports
and tests with zero network and no SDK.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional
from ._core import FakeClient, coerce_payload, resolve_client, run_check

try:  # real SDK type when available
    from agents import GuardrailFunctionOutput as _SdkOutput  # type: ignore
except Exception:  # pragma: no cover - exercised when SDK absent
    _SdkOutput = None

if _SdkOutput is not None:
    GuardrailFunctionOutput = _SdkOutput
else:
    @dataclass
    class GuardrailFunctionOutput:  # SDK-compatible fallback
        output_info: Any = None
        tripwire_triggered: bool = False

class ProveCartBlocked(Exception):
    """Raised by the sync helper on a fixable BLOCK."""
    def __init__(self, detail, response):
        super().__init__(f"ProveCart BLOCK: {detail}")
        self.detail, self.response = detail, response
class ProveCartEscalation(Exception):
    """Raised by the sync helper when the buyer must decide."""
    def __init__(self, detail, response):
        super().__init__(f"ProveCart escalation: {detail}")
        self.detail, self.response = detail, response

def _make_output(info, tripwire):
    if _SdkOutput is not None:
        return _SdkOutput(output_info=info, tripwire_triggered=tripwire)
    return GuardrailFunctionOutput(output_info=info, tripwire_triggered=tripwire)

class ProveCartGuardrail:
    """Callable guardrail. Await it (SDK style) or use ``.run_sync``."""
    def __init__(self, client_or_key=None, *, check="cart", tools=None,
                 auto_fix=False, mock=False, payload_from=None):
        self.client = resolve_client(client_or_key, mock=mock)
        self.check = check
        self.tools = list(tools) if tools else None
        self.auto_fix = bool(auto_fix)
        self.payload_from = payload_from
        self.__name__ = "provecart_guardrail"  # SDK decorators read __name__

    def _evaluate(self, raw_input):
        payload, tool_name = coerce_payload(raw_input)
        if callable(self.payload_from):
            extracted = self.payload_from(raw_input)
            if isinstance(extracted, dict):
                payload = extracted
        if self.tools is not None and tool_name is not None and tool_name not in self.tools:
            return _make_output({"provecart": "skipped",
                                 "reason": f"tool {tool_name!r} not guarded",
                                 "tool_name": tool_name}, False)
        response, decision, detail = run_check(self.client, self.check, payload)
        info = {"provecart": decision, "verdict": response.get("verdict"),
                "record_id": response.get("record_id"),
                "max_attempts": response.get("max_attempts"),
                "tool_name": tool_name, "detail": detail}
        if decision == "proceed":
            return _make_output(info, False)
        if decision == "fix":
            info["routing"] = "fix"
            info["corrections"] = detail.get("corrections") or response.get("corrections") or []
            return _make_output(info, not self.auto_fix)
        info["routing"] = "escalate"
        return _make_output(info, True)

    async def __call__(self, ctx=None, agent=None, input_data=None, **kwargs):
        # SDK guardrails are called as (ctx, agent, input); tool
        # guardrails pass differently shaped data — coerce either way.
        raw = input_data if input_data is not None else (kwargs.get("input") or kwargs.get("tool_input") or ctx)
        return self._evaluate(raw)

    def as_tool_input_guardrail(self):
        """Adapt to the SDK's tool-input guardrail (runs BEFORE the tool).

        Requires openai-agents. Mapping: proceed -> allow (tool runs);
        fixable BLOCK -> reject_content with the corrections as the
        message (tool does NOT run, the model can correct and retry);
        escalate -> raise_exception (run halts for the buyer).
        """
        from agents import ToolGuardrailFunctionOutput, tool_input_guardrail
        guardrail = self
        @tool_input_guardrail
        async def _provecart_tool_guardrail(data):
            ctx = data.context
            raw = {"tool_name": getattr(ctx, "tool_name", None),
                   "arguments": getattr(ctx, "tool_arguments", None)}
            out = guardrail._evaluate(raw)
            info = out.output_info
            decision = info.get("provecart") if isinstance(info, dict) else None
            if decision == "proceed" or decision == "skipped":
                return ToolGuardrailFunctionOutput.allow(output_info=info)
            if decision == "fix":
                import json as _json
                return ToolGuardrailFunctionOutput.reject_content(
                    "ProveCart BLOCK: do not pay yet. Apply only these "
                    "corrections and re-check: "
                    + _json.dumps(info.get("corrections") or []),
                    output_info=info)
            return ToolGuardrailFunctionOutput.raise_exception(output_info=info)
        return _provecart_tool_guardrail

    def run_sync(self, raw_input=None, **kwargs):
        raw = raw_input if raw_input is not None else kwargs.get("input")
        return self._evaluate(raw)

    # convenience for non-SDK callers who prefer exceptions
    def check_or_raise(self, raw_input):
        out = self._evaluate(raw_input)
        info = out.output_info if isinstance(out.output_info, dict) else {}
        if not out.tripwire_triggered and info.get("provecart") in ("proceed",):
            return info
        if info.get("routing") == "fix" and self.auto_fix:
            return info
        if info.get("routing") == "fix":
            raise ProveCartBlocked(info.get("detail"), info)
        if out.tripwire_triggered:
            raise ProveCartEscalation(info.get("detail"), info)
        return info

def provecart_guardrail(client_or_key=None, *, check="cart", tools=None,
                        auto_fix=False, mock=False, payload_from=None):
    """Factory: return a guardrail callable for the Agents SDK.

    Usage (SDK): attach the returned callable wherever the SDK takes
    a guardrail function (output guardrails / tool guardrails lists);
    it is an async callable returning GuardrailFunctionOutput.
    ``client_or_key``: injected client, duck-typed callable, API key
    string (live, needs the ``provecart`` package), ``"mock"``, or
    None + ``mock=True`` for the offline fake.
    """
    return ProveCartGuardrail(client_or_key, check=check, tools=tools,
                              auto_fix=auto_fix, mock=mock,
                              payload_from=payload_from)

__all__ = ["ProveCartGuardrail", "provecart_guardrail",
           "GuardrailFunctionOutput", "ProveCartBlocked", "ProveCartEscalation"]
