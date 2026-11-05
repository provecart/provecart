
"""LangGraph integration: check state BEFORE the payment node.

Two shapes, same verdict contract (MATCH -> proceed, BLOCK with known
corrections -> fix, REVIEW / unfixable BLOCK -> escalate):

1. ``provecart_check_node(client, ...)`` — a StateGraph node factory.
   The node reads the cart/order from state, checks it, and writes
   ``provecart_decision`` / ``provecart_verdict`` /
   ``provecart_corrections`` / ``provecart_record_id`` back into
   state. Pair it with :func:`provecart_route` in
   ``add_conditional_edges`` to reach proceed / fix / escalate nodes.

2. ``guard_purchase_tool(fn, client, ...)`` — wraps any purchase
   tool callable so the check runs first. On proceed the tool runs;
   on fix/escalate it raises (or calls your handler) and the tool
   body never executes.

Works with or without langgraph installed: the node is a plain
``state -> partial-state`` function, which is exactly what
StateGraph consumes.
"""
from __future__ import annotations
from functools import wraps
from typing import Any, Callable, Optional
from ._core import resolve_client, run_check

class ProveCartBlocked(Exception):
    """Fixable BLOCK: corrections are on ``.corrections``."""
    def __init__(self, detail, response):
        super().__init__(f"ProveCart BLOCK: {detail}")
        self.detail, self.response = detail, response
        self.corrections = (detail or {}).get("corrections") or (response or {}).get("corrections")
class ProveCartEscalation(Exception):
    """REVIEW or unfixable BLOCK: the buyer must decide."""
    def __init__(self, detail, response):
        super().__init__(f"ProveCart escalation: {detail}")
        self.detail, self.response = detail, response

def _payload_from_state(state, cart_key, payload_from):
    if callable(payload_from):
        return payload_from(state)
    if isinstance(state, dict):
        for key in (cart_key, "cart", "order", "booking", "reservation", "payload"):
            val = state.get(key)
            if isinstance(val, dict):
                return val
        return dict(state)
    return {"value": state}

def provecart_check_node(client=None, *, check="cart", cart_key="cart",
                         mock=False, payload_from=None, decision_key="provecart_decision"):
    """Return a StateGraph node function ``node(state) -> dict``."""
    resolved = resolve_client(client, mock=mock)
    def node(state):
        payload = _payload_from_state(state, cart_key, payload_from)
        response, decision, detail = run_check(resolved, check, payload)
        update = {decision_key: decision,
                  "provecart_verdict": response.get("verdict"),
                  "provecart_record_id": response.get("record_id"),
                  "provecart_max_attempts": response.get("max_attempts"),
                  "provecart_response": response,
                  "provecart_detail": detail}
        if decision == "fix":
            update["provecart_corrections"] = detail.get("corrections") or response.get("corrections") or []
        return update
    node.__name__ = "provecart_check"
    return node

def provecart_route(state, *, decision_key="provecart_decision"):
    """Conditional-edge router: returns proceed / fix / escalate.

    Missing or unknown decision escalates — never proceeds on doubt.
    """
    if isinstance(state, dict):
        decision = state.get(decision_key)
        if decision in ("proceed", "fix", "escalate"):
            return decision
    return "escalate"

def guard_purchase_tool(tool_fn=None, client=None, *, check="cart", mock=False,
                        payload_from=None, on_fix=None, on_escalate=None):
    """Wrap a purchase callable with the pre-payment check.

    Usable bare (``guard_purchase_tool(fn, client)``) or as a
    decorator factory. The wrapped callable takes the cart payload
    as its first argument (dict) or a ``cart=``/``payload=`` kwarg,
    unless ``payload_from(*args, **kwargs)`` extracts it.
    """
    resolved = resolve_client(client, mock=mock)
    def decorate(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if callable(payload_from):
                payload = payload_from(*args, **kwargs)
            elif args and isinstance(args[0], dict):
                payload = args[0]
            else:
                payload = kwargs.get("cart") or kwargs.get("payload") or kwargs.get("order") or {}
            response, decision, detail = run_check(resolved, check, payload if isinstance(payload, dict) else {"value": payload})
            if decision == "proceed":
                return fn(*args, **kwargs)
            if decision == "fix":
                if on_fix is not None:
                    return on_fix(detail, response)
                raise ProveCartBlocked(detail, response)
            if on_escalate is not None:
                return on_escalate(detail, response)
            raise ProveCartEscalation(detail, response)
        return wrapper
    if tool_fn is not None:
        return decorate(tool_fn)
    return decorate

# alias matching the task vocabulary
wrap_purchase_tool = guard_purchase_tool
__all__ = ["provecart_check_node", "provecart_route", "guard_purchase_tool",
           "wrap_purchase_tool", "ProveCartBlocked", "ProveCartEscalation"]
