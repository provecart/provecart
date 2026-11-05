"""Offline tests for provecart-adk. No network; ADK stubbed if absent."""
import asyncio
import sys
import types

# Stub google.adk plugin base if the real package is not installed,
# so the plugin class can be imported and exercised offline.
try:
    import google.adk.plugins.base_plugin  # noqa: F401
    HAS_ADK = True
except Exception:
    HAS_ADK = False
    google = types.ModuleType("google")
    adk = types.ModuleType("google.adk")
    plugins = types.ModuleType("google.adk.plugins")
    base_plugin = types.ModuleType("google.adk.plugins.base_plugin")

    class BasePlugin:
        def __init__(self, name=None):
            self.name = name

    base_plugin.BasePlugin = BasePlugin
    plugins.base_plugin = base_plugin
    adk.plugins = plugins
    google.adk = adk
    sys.modules.setdefault("google", google)
    sys.modules["google.adk"] = adk
    sys.modules["google.adk.plugins"] = plugins
    sys.modules["google.adk.plugins.base_plugin"] = base_plugin

sys.path.insert(0, "src")

from provecart_adk import (  # noqa: E402
    FakeProveCartClient, ProveCartGuard, ProveCartPlugin,
    make_before_tool_callback, route_verdict,
)


class Tool:
    def __init__(self, name):
        self.name = name


CART_ARGS = {"mandate_id": "m1", "merchant": {"name": "Shop"},
             "items": [{"name": "Chair"}], "total_price": 10}


def test_route_match_proceeds():
    assert route_verdict({"verdict": "MATCH", "record_id": "r1"})[0] == "proceed"


def test_route_block_known_fix():
    d, detail = route_verdict({"verdict": "BLOCK", "record_id": "r",
                               "corrections": [{"action": "remove_item"}],
                               "max_attempts": 3})
    assert d == "fix" and detail["max_attempts"] == 3


def test_route_block_unknown_escalates():
    d, _ = route_verdict({"verdict": "BLOCK",
                          "corrections": [{"action": "widen_budget"}]})
    assert d == "escalate"


def test_route_review_and_unknown_escalate():
    assert route_verdict({"verdict": "REVIEW"})[0] == "escalate"
    assert route_verdict({"verdict": "???"})[0] == "escalate"
    assert route_verdict({})[0] == "escalate"


def test_non_purchase_tool_passes_without_check():
    fake = FakeProveCartClient()
    guard = ProveCartGuard(fake)
    assert guard.before_tool(Tool("search_catalog"), {"q": "x"}) is None
    assert fake.calls == []


def test_match_lets_tool_run():
    fake = FakeProveCartClient()
    cb = make_before_tool_callback(ProveCartGuard(fake))
    assert cb(tool=Tool("place_order"), args=CART_ARGS, tool_context=None) is None
    assert fake.calls and fake.calls[0][0] == "cart"


def test_block_returns_refusal_dict_with_corrections():
    fake = FakeProveCartClient({"verdict": "BLOCK", "record_id": "r9",
                                "max_attempts": 2,
                                "corrections": [{"action": "reduce_quantity"}]})
    cb = make_before_tool_callback(ProveCartGuard(fake))
    out = cb(tool=Tool("checkout"), args=CART_ARGS, tool_context=None)
    assert out["provecart_blocked"] is True
    assert out["provecart_decision"] == "fix"
    assert out["corrections"] == [{"action": "reduce_quantity"}]
    assert out["record_id"] == "r9"


def test_review_escalates_and_booking_and_reservation_kinds():
    fake = FakeProveCartClient({"verdict": "REVIEW", "record_id": "r2",
                                "corrections": []})
    guard = ProveCartGuard(fake)
    out = guard.before_tool(Tool("book_flight"), {"booking": {"mandate_id": "m"}})
    assert out["provecart_decision"] == "escalate" and out["check_kind"] == "booking"
    out = guard.before_tool(Tool("reserve_table"), {"mandate_id": "m"})
    assert out["check_kind"] == "reservation"
    assert [c[0] for c in fake.calls] == ["booking", "reservation"]


def test_check_failure_escalates_not_proceeds():
    class Boom:
        def check_cart(self, **kw):
            raise RuntimeError("down")
    guard = ProveCartGuard(Boom())
    out = guard.before_tool(Tool("place_order"), CART_ARGS)
    assert out["provecart_decision"] == "escalate"


def test_client_route_verdict_is_preferred():
    class Own:
        def check_cart(self, **kw):
            return {"verdict": "MATCH", "record_id": "x"}
        def route_verdict(self, response):
            return "escalate", {"reason": "house rule"}
    guard = ProveCartGuard(Own())
    out = guard.before_tool(Tool("place_order"), CART_ARGS)
    assert out["provecart_decision"] == "escalate"


def test_plugin_callback_signature_both_arg_names():
    fake = FakeProveCartClient()
    plugin = ProveCartPlugin(client=fake)
    run = asyncio.get_event_loop().run_until_complete
    assert run(plugin.before_tool_callback(
        tool=Tool("place_order"), tool_args=CART_ARGS, tool_context=None)) is None
    assert run(plugin.before_tool_callback(
        tool=Tool("place_order"), args=CART_ARGS, tool_context=None)) is None
    assert len(fake.calls) == 2
    print("HAS_REAL_ADK:", HAS_ADK)
