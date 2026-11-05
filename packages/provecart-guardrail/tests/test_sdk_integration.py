"""Real OpenAI Agents SDK integration (skipped when SDK absent)."""
import asyncio, json, sys
import pathlib as _pl; sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / "src"))
import pytest
agents = pytest.importorskip("agents")
from provecart_guardrail import provecart_guardrail, FakeClient
from provecart_guardrail._core import match_response, block_fixable_response, review_response

CART = {"mandate_id": "m1", "merchant": {"name": "S"}, "items": [], "total_price": 10.0}

def test_output_is_real_sdk_type():
    out = asyncio.run(provecart_guardrail(FakeClient(response=match_response()))(None, None, CART))
    assert isinstance(out, agents.GuardrailFunctionOutput)
    assert out.tripwire_triggered is False

def test_wraps_as_output_guardrail():
    g = provecart_guardrail(FakeClient(response=review_response()))
    wrapped = agents.output_guardrail(g)
    assert wrapped is not None and hasattr(wrapped, "run")

def test_tool_input_guardrail_adapter():
    from agents.tool_context import ToolContext
    from agents import ToolInputGuardrailData
    for resp, want in [(match_response(), "allow"),
                       (block_fixable_response(), "reject_content"),
                       (review_response(), "raise_exception")]:
        g = provecart_guardrail(FakeClient(response=resp), tools=["pay"])
        tool_guardrail = g.as_tool_input_guardrail()
        ctx = ToolContext(context=None, tool_name="pay", tool_call_id="c1",
                          tool_arguments=json.dumps(CART))
        data = ToolInputGuardrailData(context=ctx, agent=None)
        out = tool_guardrail.run(data)
        if asyncio.iscoroutine(out):
            out = asyncio.run(out)
        fn_out = getattr(out, "output", out)
        behavior = getattr(fn_out, "behavior", None)
        btype = getattr(behavior, "type", None) or str(behavior)
        assert want in str(btype), f"expected {want}, got {out!r}"
