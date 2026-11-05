"""ProveCart pre-action hook for Google ADK.

Intercepts the moment before a purchase tool runs, checks the
pending order, booking or reservation against the customer's signed
mandate, and lets the tool run only on a MATCH.

Verdict routing (same semantics as the shared ProveCart client):

  MATCH              -> proceed (return None; ADK runs the tool)
  BLOCK + known fixes -> do not run the tool; return a refusal dict
                        carrying the corrections, so the agent can
                        apply only fixes inside the customer's
                        existing authorization and re-check
  BLOCK otherwise,
  REVIEW, unknown    -> do not run the tool; return a refusal dict
                        that escalates to the customer

In ADK, returning a dict from ``before_tool_callback`` skips the
tool call and uses that dict as the tool result. That documented
refusal path is what this package uses for every non-proceed case.

The client is injected and duck-typed. Any object with
``check_cart`` / ``check_booking`` / ``check_reservation`` methods
returning a dict with ``verdict``, ``corrections``, ``record_id``
and ``max_attempts`` works, as does an object exposing
``route_verdict(response) -> (decision, detail)``. If the client
supplies its own ``route_verdict`` it is used; otherwise the routing
in this module is used. A client with only the older
``verify_cart`` shape is adapted for cart checks.

No network call happens on import.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional, Tuple

__version__ = "0.1.0"
__all__ = [
    "KNOWN_ACTIONS",
    "DEFAULT_TOOL_KINDS",
    "ProveCartGuard",
    "FakeProveCartClient",
    "make_before_tool_callback",
    "route_verdict",
]

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

# Default purchase-tool names -> check kind. Override per guard.
DEFAULT_TOOL_KINDS: Dict[str, str] = {
    "place_order": "cart",
    "checkout": "cart",
    "create_order": "cart",
    "capture_payment": "cart",
    "pay": "cart",
    "purchase": "cart",
    "buy": "cart",
    "create_booking": "booking",
    "book_flight": "booking",
    "book_hotel": "booking",
    "book": "booking",
    "make_reservation": "reservation",
    "create_reservation": "reservation",
    "reserve_table": "reservation",
    "reserve": "reservation",
}

_CHECK_METHOD = {
    "cart": "check_cart",
    "booking": "check_booking",
    "reservation": "check_reservation",
}
_PAYLOAD_KEYS = {"cart": "cart", "booking": "booking", "reservation": "reservation"}


def route_verdict(response: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Return (decision, detail); decision in {proceed, fix, escalate}.

    'fix' is returned only when the verdict is BLOCK and every
    correction is a known action. Anything else non-MATCH escalates.
    """
    verdict = (response or {}).get("verdict")
    if verdict == "MATCH":
        return "proceed", {"record_id": response.get("record_id")}
    if verdict == "BLOCK":
        corrections = response.get("corrections") or []
        if corrections and all(
            isinstance(c, Mapping) and c.get("action") in KNOWN_ACTIONS
            for c in corrections
        ):
            return "fix", {
                "corrections": list(corrections),
                "record_id": response.get("record_id"),
                "max_attempts": response.get("max_attempts"),
            }
        return "escalate", {
            "reason": "BLOCK without usable corrections",
            "record_id": response.get("record_id"),
        }
    return "escalate", {
        "reason": f"verdict {verdict} needs the buyer",
        "record_id": response.get("record_id"),
    }


def _tool_name(tool: Any) -> str:
    if isinstance(tool, str):
        return tool
    return getattr(tool, "name", "") or str(tool)


class ProveCartGuard:
    """Framework-agnostic core; the ADK adapters below call it."""

    def __init__(
        self,
        client: Any,
        tool_kinds: Optional[Mapping[str, str]] = None,
        extractor: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        if client is None:
            raise ValueError("ProveCartGuard requires an injected client")
        self.client = client
        self.tool_kinds = dict(tool_kinds) if tool_kinds is not None else dict(DEFAULT_TOOL_KINDS)
        self.extractor = extractor

    def kind_for(self, tool: Any) -> Optional[str]:
        return self.tool_kinds.get(_tool_name(tool))

    def extract(self, kind: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if self.extractor is not None:
            return dict(self.extractor(kind, dict(args)))
        nested = args.get(_PAYLOAD_KEYS[kind])
        if isinstance(nested, Mapping):
            payload = dict(nested)
            # Mandate / linkage fields may sit beside the nested payload.
            for key in ("mandate_id", "previous_record_id"):
                if key in args and key not in payload:
                    payload[key] = args[key]
            return payload
        return dict(args)

    def check(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        method_name = _CHECK_METHOD[kind]
        method = getattr(self.client, method_name, None)
        if callable(method):
            return dict(method(**payload))
        if kind == "cart" and callable(getattr(self.client, "verify_cart", None)):
            return dict(self.client.verify_cart(**payload))
        raise TypeError(f"client does not provide {method_name}()")

    def route(self, response: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        client_route = getattr(self.client, "route_verdict", None)
        if callable(client_route):
            decision, detail = client_route(response)
            return str(decision), dict(detail or {})
        return route_verdict(response)

    def before_tool(self, tool: Any, args: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Return None to let the tool run, or a refusal dict to skip it."""
        kind = self.kind_for(tool)
        if kind is None:
            return None
        payload = self.extract(kind, dict(args or {}))
        try:
            response = self.check(kind, payload)
        except Exception as exc:  # a failed check never lets a purchase through
            return self._refusal(kind, tool, None, "escalate",
                                 {"reason": f"check failed: {exc}"})
        decision, detail = self.route(response)
        if decision == "proceed":
            return None
        return self._refusal(kind, tool, response, decision, detail)

    @staticmethod
    def _refusal(kind, tool, response, decision, detail):
        response = response or {}
        return {
            "provecart_blocked": True,
            "provecart_decision": decision,
            "verdict": response.get("verdict"),
            "check_kind": kind,
            "tool": _tool_name(tool),
            "corrections": response.get("corrections") or detail.get("corrections") or [],
            "record_id": response.get("record_id") or detail.get("record_id"),
            "max_attempts": response.get("max_attempts") or detail.get("max_attempts"),
            "detail": detail,
            "error": (
                "ProveCart check did not return MATCH, so the purchase "
                "tool was not run. On 'fix', apply only the listed "
                "corrections inside the customer's existing authorization "
                "and re-check with previous_record_id. On 'escalate', "
                "stop and ask the customer."
            ),
        }


def make_before_tool_callback(guard: ProveCartGuard):
    """Build an ADK agent-level ``before_tool_callback``.

    Documented ADK signature:
    ``(tool, args, tool_context) -> Optional[dict]`` — returning None
    lets the tool run; returning a dict skips the tool and that dict
    becomes the tool result.
    """
    def before_tool_callback(tool=None, args=None, tool_context=None, **_kw):
        return guard.before_tool(tool, args or {})

    return before_tool_callback


try:  # Real plugin base when google-adk is installed; stub-safe otherwise.
    from google.adk.plugins.base_plugin import BasePlugin as _BasePlugin
    _HAS_ADK = True
except Exception:  # pragma: no cover - exercised in stubbed environments
    _BasePlugin = object  # type: ignore
    _HAS_ADK = False


class ProveCartPlugin(_BasePlugin):  # type: ignore[misc]
    """ADK plugin form. Register once on the Runner / App.

    Plugin signature in current ADK:
    ``async before_tool_callback(*, tool, tool_args, tool_context)``
    returning None to proceed or a dict to skip the tool. Older /
    alternate callers may pass ``args`` instead of ``tool_args``;
    both are accepted.
    """

    def __init__(self, guard: Optional[ProveCartGuard] = None, *,
                 client: Any = None, **guard_kwargs):
        if _HAS_ADK:
            try:
                super().__init__(name="provecart")
            except TypeError:
                super().__init__()
        self.guard = guard or ProveCartGuard(client, **guard_kwargs)

    async def before_tool_callback(self, *, tool=None, tool_args=None,
                                   args=None, tool_context=None, **_kw):
        payload = tool_args if tool_args is not None else args
        return self.guard.before_tool(tool, payload or {})


class FakeProveCartClient:
    """Offline fake for examples and tests. No network, ever.

    Pass a fixed response dict, or a callable payload -> response.
    Records every call in ``.calls`` as (kind, payload).
    """

    def __init__(self, response=None):
        self._response = response if response is not None else {
            "verdict": "MATCH", "corrections": [], "record_id": "rec_mock_1",
            "max_attempts": 3,
        }
        self.calls = []

    def _handle(self, kind, **payload):
        self.calls.append((kind, payload))
        if callable(self._response):
            return dict(self._response(payload))
        return dict(self._response)

    def check_cart(self, **payload):
        return self._handle("cart", **payload)

    def check_booking(self, **payload):
        return self._handle("booking", **payload)

    def check_reservation(self, **payload):
        return self._handle("reservation", **payload)

    # Deliberately no route_verdict: exercises this module's routing.
