import asyncio, sys
import pathlib as _pl; sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / "src"))
import pytest
from provecart_guardrail import provecart_guardrail, FakeClient, GuardrailFunctionOutput
from provecart_guardrail._core import match_response, block_fixable_response, block_unfixable_response, review_response

CART = {"mandate_id": "m1", "merchant": {"name": "S"}, "items": [], "total_price": 10.0}
def run(g, raw):
    return asyncio.run(g(None, None, raw))

def test_match_proceeds():
    out = run(provecart_guardrail(FakeClient(response=match_response())), CART)
    assert out.tripwire_triggered is False and out.output_info["verdict"] == "MATCH"

def test_review_trips():
    out = run(provecart_guardrail(FakeClient(response=review_response())), CART)
    assert out.tripwire_triggered is True and out.output_info["routing"] == "escalate"

def test_block_fixable_trips_by_default_and_surfaces_corrections():
    out = run(provecart_guardrail(FakeClient(response=block_fixable_response())), CART)
    assert out.tripwire_triggered is True and out.output_info["corrections"]

def test_block_fixable_no_trip_with_auto_fix():
    out = run(provecart_guardrail(FakeClient(response=block_fixable_response()), auto_fix=True), CART)
    assert out.tripwire_triggered is False and out.output_info["routing"] == "fix"

def test_block_unfixable_trips_even_with_auto_fix():
    out = run(provecart_guardrail(FakeClient(response=block_unfixable_response()), auto_fix=True), CART)
    assert out.tripwire_triggered is True

def test_unlisted_tool_skips_check():
    c = FakeClient(response=review_response())
    out = run(provecart_guardrail(c, tools=["pay"]), {"tool_name": "search", "arguments": CART})
    assert out.tripwire_triggered is False and c.calls == []

def test_callable_client_and_verify_cart_adapter():
    out = run(provecart_guardrail(lambda payload: match_response()), CART)
    assert out.tripwire_triggered is False
    class Old:
        def verify_cart(self, **kw): return review_response()
    out = run(provecart_guardrail(Old()), CART)
    assert out.tripwire_triggered is True

def test_mock_default_is_offline_fake():
    out = run(provecart_guardrail(mock=True), CART)
    assert out.tripwire_triggered is False

def test_output_shape():
    out = run(provecart_guardrail(FakeClient()), CART)
    assert isinstance(out, GuardrailFunctionOutput)
    assert hasattr(out, "output_info") and hasattr(out, "tripwire_triggered")

def test_unknown_verdict_escalates():
    out = run(provecart_guardrail(FakeClient(response={"verdict": "WAT", "record_id": "r"})), CART)
    assert out.tripwire_triggered is True
