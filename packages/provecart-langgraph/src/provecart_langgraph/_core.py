
"""Shared ProveCart check plumbing (self-contained, no network on import).

A *client* is any of:
  * an object with ``check_cart`` / ``check_booking`` /
    ``check_reservation`` methods returning verdict dicts
    ``{verdict, corrections[], record_id, max_attempts, ...}``,
  * an object with the older ``verify_cart(...)`` method,
  * a plain callable taking a payload dict and returning a verdict
    dict, or
  * an object exposing ``route_verdict(response)`` (used when present).
When no client is supplied the deterministic :class:`FakeClient` is
used, so examples and tests run fully offline. Live mode is explicit
opt-in only: pass a real client, or pass an API-key string and this
module lazily constructs ``provecart.ProveCartClient``.
"""
from __future__ import annotations
import json

KNOWN_ACTIONS = {
    "remove_item", "replace_item", "change_variant", "reduce_quantity",
    "reduce_total", "change_currency", "correct_traveler_name",
    "change_airport", "change_travel_date", "change_departure_time",
    "add_itinerary", "rebuild_itinerary", "change_cabin",
    "change_fare_terms", "add_hotel_stay", "change_room",
    "change_provider", "change_location", "change_date", "change_time",
    "change_party_size", "correct_reservation_name", "reduce_deposit",
    "change_cancellation_terms",
}

def route_verdict(response):
    """(decision, detail); decision in {proceed, fix, escalate}.

    MATCH -> proceed. BLOCK -> fix only when every correction is a
    known action. REVIEW / anything unknown -> escalate. Never guess,
    never widen the customer's authorization.
    """
    if not isinstance(response, dict):
        return "escalate", {"reason": "non-dict verdict response"}
    verdict = response.get("verdict")
    if verdict == "MATCH":
        return "proceed", {"record_id": response.get("record_id")}
    if verdict == "BLOCK":
        corrections = response.get("corrections") or []
        if corrections and all(isinstance(c, dict) and c.get("action") in KNOWN_ACTIONS for c in corrections):
            return "fix", {"corrections": corrections,
                           "record_id": response.get("record_id"),
                           "max_attempts": response.get("max_attempts")}
        return "escalate", {"reason": "BLOCK without usable corrections",
                            "record_id": response.get("record_id")}
    return "escalate", {"reason": f"verdict {verdict} needs the buyer",
                        "record_id": response.get("record_id")}

class FakeClient:
    """Deterministic offline client. Default reply is MATCH.

    Pass ``responses=[...]`` to script verdict dicts in order, or a
    single ``response=`` dict, or ``handler=callable(payload)->dict``.
    Records every payload in ``.calls``.
    """
    def __init__(self, responses=None, response=None, handler=None):
        self._queue = list(responses) if responses is not None else None
        self._response = response
        self._handler = handler
        self.calls = []
    def _next(self, kind, payload):
        self.calls.append({"kind": kind, "payload": payload})
        if self._handler is not None:
            return self._handler(payload)
        if self._queue:
            return self._queue.pop(0)
        if self._response is not None:
            return dict(self._response)
        return {"verdict": "MATCH", "corrections": [], "record_id": "rec_mock_match", "max_attempts": 3}
    def check_cart(self, *args, **kwargs):
        return self._next("cart", kwargs or (args[0] if args else {}))
    def check_booking(self, *args, **kwargs):
        return self._next("booking", kwargs or (args[0] if args else {}))
    def check_reservation(self, *args, **kwargs):
        return self._next("reservation", kwargs or (args[0] if args else {}))
    # alias in the older starter shape
    def verify_cart(self, *args, **kwargs):
        return self.check_cart(*args, **kwargs)
    @staticmethod
    def route_verdict(response):
        return route_verdict(response)

# convenient scripted verdicts
def match_response(record_id="rec_mock_match"):
    return {"verdict": "MATCH", "corrections": [], "record_id": record_id, "max_attempts": 3}
def block_fixable_response(record_id="rec_mock_block"):
    return {"verdict": "BLOCK", "record_id": record_id, "max_attempts": 3,
            "corrections": [{"action": "reduce_quantity", "field": "quantity", "expected": 1, "actual": 2},
                            {"action": "reduce_total", "field": "total_price", "expected": 299.0, "actual": 378.0}]}
def block_unfixable_response(record_id="rec_mock_block2"):
    return {"verdict": "BLOCK", "record_id": record_id, "max_attempts": 3,
            "corrections": [{"action": "some_unknown_action", "field": "x"}]}
def review_response(record_id="rec_mock_review"):
    return {"verdict": "REVIEW", "corrections": [], "record_id": record_id, "max_attempts": 3}

def resolve_client(client_or_key=None, mock=False):
    """Return a client object. ``mock=True`` (or None / 'mock') -> FakeClient."""
    if mock or client_or_key is None or client_or_key == "mock":
        return FakeClient()
    if isinstance(client_or_key, FakeClient):
        return client_or_key
    if isinstance(client_or_key, str):
        # explicit live opt-in: an API key string
        try:
            from provecart import ProveCartClient  # loose dependency, lazy
        except Exception as exc:
            raise RuntimeError(
                "Passing an API key needs the 'provecart' package installed, "
                "or inject a client object / callable instead.") from exc
        return ProveCartClient(api_key=client_or_key)
    return client_or_key

def run_check(client, check, payload):
    """Dispatch one check. Returns (response_dict, decision, detail)."""
    if not isinstance(payload, dict):
        payload = {"value": payload}
    response = None
    method_name = {"cart": "check_cart", "booking": "check_booking",
                   "reservation": "check_reservation"}.get(check, "check_cart")
    method = getattr(client, method_name, None)
    if method is None and check == "cart":
        method = getattr(client, "verify_cart", None)
    if callable(method):
        try:
            response = method(**payload)
        except TypeError:
            response = method(payload)
    elif callable(client):
        response = client(payload)
    else:
        raise TypeError("client must expose check_cart/check_booking/check_reservation, verify_cart, or be callable")
    if not isinstance(response, dict):
        raise TypeError("ProveCart check must return a verdict dict")
    router = getattr(client, "route_verdict", None)
    if callable(router):
        try:
            decision, detail = router(response)
        except Exception:
            decision, detail = route_verdict(response)
    else:
        decision, detail = route_verdict(response)
    return response, decision, detail

def coerce_payload(raw):
    """Best-effort extraction of a check payload dict from many shapes."""
    if raw is None:
        return {}, None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return coerce_payload(parsed)
        except Exception:
            return {"value": raw}, None
    if isinstance(raw, dict):
        tool_name = raw.get("tool_name") or raw.get("toolName") or raw.get("name")
        for key in ("cart", "booking", "reservation", "order", "payload", "arguments", "tool_input", "tool_arguments", "input", "data"):
            inner = raw.get(key)
            if isinstance(inner, (dict, str)):
                payload, _ = coerce_payload(inner)
                kind = {"cart": "cart", "booking": "booking", "reservation": "reservation", "order": "cart"}.get(key)
                return payload, (kind or tool_name)
        return dict(raw), tool_name
    # SDK / framework objects: read common attributes without importing them
    for attr in ("tool_arguments", "arguments", "tool_input", "input", "data"):
        val = getattr(raw, attr, None)
        if val is not None:
            payload, _ = coerce_payload(val)
            return payload, getattr(raw, "tool_name", None) or getattr(raw, "name", None)
    return {"value": raw}, getattr(raw, "tool_name", None)
