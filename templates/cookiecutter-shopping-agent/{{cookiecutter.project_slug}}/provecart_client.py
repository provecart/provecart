"""ProveCart client + verdict routing, shared by the framework examples.

Self-contained (standard library only). Implements the consumer rules
of the Agent Correction Format (ACF v0.2, com.provecart.conformity):

  MATCH             -> proceed to payment.
  BLOCK + fixes     -> apply ONLY repairs that bring the cart INTO the
                       buyer's existing authorization, then resubmit
                       as a new check carrying previous_record_id,
                       within max_attempts.
  REVIEW / unknown  -> stop and escalate to the buyer. Never guess,
  action               never widen the authorization.

API contract (https://api.provecart.com, X-API-Key header):
  POST /mandates  {user_id, item_description, item_keywords, category,
                   max_total_price, currency, max_quantity, expires_at,
                   ...} -> signed mandate (use its "id")
  POST /verify    {mandate_id, merchant{name, domain}, items[{name,
                   variant, quantity, unit_price, category, brand}],
                   total_price, currency, tax, shipping, fees,
                   previous_record_id?, cart_changed?}
                  -> {verdict, corrections[], max_attempts, record_id,
                      verdict_token, ...}
"""
import json
import urllib.error
import urllib.request

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


class ProveCartClient:
    def __init__(self, api_key, base_url="https://api.provecart.com"):
        self.api_key = api_key
        self.base = base_url.rstrip("/")

    def _post(self, path, body):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json",
                     "X-API-Key": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}

    def create_mandate(self, **fields):
        status, out = self._post("/mandates", fields)
        if status != 200:
            raise RuntimeError(f"mandate creation failed: {status} {out}")
        return out

    def verify_cart(self, mandate_id, merchant, items, total_price,
                    currency="USD", tax=0.0, shipping=0.0, fees=0.0,
                    previous_record_id=None, cart_changed=False):
        body = {"mandate_id": mandate_id, "merchant": merchant,
                "items": items, "total_price": total_price,
                "currency": currency, "tax": tax, "shipping": shipping,
                "fees": fees, "cart_changed": cart_changed}
        if previous_record_id:
            body["previous_record_id"] = previous_record_id
        status, out = self._post("/verify", body)
        if status != 200:
            raise RuntimeError(f"verify failed: {status} {out}")
        return out


def route_verdict(response):
    """Return (decision, detail): decision is 'proceed', 'fix' or
    'escalate'. 'fix' is returned only when every correction is a
    known action; anything else escalates to the buyer."""
    verdict = response.get("verdict")
    if verdict == "MATCH":
        return "proceed", {"record_id": response.get("record_id")}
    if verdict == "BLOCK":
        corrections = response.get("corrections") or []
        if corrections and all(c.get("action") in KNOWN_ACTIONS
                                for c in corrections):
            return "fix", {"corrections": corrections,
                           "record_id": response.get("record_id"),
                           "max_attempts": response.get("max_attempts")}
        return "escalate", {"reason": "BLOCK without usable corrections",
                            "record_id": response.get("record_id")}
    return "escalate", {"reason": f"verdict {verdict} needs the buyer",
                        "record_id": response.get("record_id")}
