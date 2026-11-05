import sys
import pathlib as _pl; sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / "src"))
import pytest
from provecart_langgraph import (provecart_check_node, provecart_route,
    guard_purchase_tool, FakeClient, ProveCartBlocked, ProveCartEscalation)
from provecart_langgraph._core import match_response, block_fixable_response, block_unfixable_response, review_response

CART = {"mandate_id": "m1", "merchant": {"name": "S"}, "items": [], "total_price": 10.0}

def test_node_match_proceeds():
    u = provecart_check_node(FakeClient(response=match_response()))({"cart": CART})
    assert u["provecart_decision"] == "proceed" and provecart_route(u) == "proceed"

def test_node_fix_carries_corrections():
    u = provecart_check_node(FakeClient(response=block_fixable_response()))({"cart": CART})
    assert u["provecart_decision"] == "fix" and u["provecart_corrections"] and provecart_route(u) == "fix"

def test_node_review_and_unfixable_escalate():
    for resp in (review_response(), block_unfixable_response()):
        u = provecart_check_node(FakeClient(response=resp))({"cart": CART})
        assert u["provecart_decision"] == "escalate" and provecart_route(u) == "escalate"

def test_route_missing_decision_escalates():
    assert provecart_route({}) == "escalate"

def test_node_mock_default():
    u = provecart_check_node(mock=True)({"cart": CART})
    assert u["provecart_decision"] == "proceed"

def test_node_callable_client():
    u = provecart_check_node(lambda payload: review_response())({"cart": CART})
    assert u["provecart_decision"] == "escalate"

def test_tool_guard_proceeds_on_match():
    calls = []
    fn = guard_purchase_tool(lambda cart: calls.append(cart) or "paid", FakeClient(response=match_response()))
    assert fn(CART) == "paid" and calls == [CART]

def test_tool_guard_blocks_and_never_runs_tool():
    calls = []
    fn = guard_purchase_tool(lambda cart: calls.append(cart), FakeClient(response=block_fixable_response()))
    with pytest.raises(ProveCartBlocked):
        fn(CART)
    assert calls == []

def test_tool_guard_escalates_on_review():
    fn = guard_purchase_tool(lambda cart: "paid", FakeClient(response=review_response()))
    with pytest.raises(ProveCartEscalation):
        fn(CART)

def test_tool_guard_custom_handler():
    fn = guard_purchase_tool(lambda cart: "paid", FakeClient(response=block_fixable_response()),
                             on_fix=lambda detail, resp: "needs-fix")
    assert fn(CART) == "needs-fix"

def test_real_langgraph_graph_if_available():
    lg = pytest.importorskip("langgraph.graph")
    from typing_extensions import TypedDict
    class S(TypedDict, total=False):
        cart: dict; provecart_decision: str; provecart_verdict: str
        provecart_record_id: str; provecart_max_attempts: int
        provecart_response: dict; provecart_detail: dict; provecart_corrections: list
        paid: bool
    g = lg.StateGraph(S)
    g.add_node("check", provecart_check_node(FakeClient(response=match_response())))
    g.add_node("pay", lambda s: {"paid": True})
    g.add_node("ask", lambda s: {"paid": False})
    g.add_edge(lg.START, "check")
    g.add_conditional_edges("check", provecart_route, {"proceed": "pay", "fix": "ask", "escalate": "ask"})
    g.add_edge("pay", lg.END); g.add_edge("ask", lg.END)
    out = g.compile().invoke({"cart": CART})
    assert out["paid"] is True and out["provecart_decision"] == "proceed"
