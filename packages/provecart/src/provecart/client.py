"""ProveCart client + verdict routing.

Self-contained (standard library only). Implements the consumer rules
of the Agent Correction Format (ACF v0.2, com.provecart.conformity):

  MATCH             -> proceed to payment (or ticket issuance).
  BLOCK + fixes     -> apply ONLY repairs that bring the transaction
                       INTO the buyer's existing authorization, then
                       resubmit as a new check carrying
                       previous_record_id, within max_attempts.
  REVIEW / unknown  -> stop and escalate to the buyer. Never guess,
  action               never widen the authorization.

API contract (https://api.provecart.com, X-API-Key header):
  POST /mandates              -> signed cart mandate (use its "id")
  POST /verify                -> cart verdict
  POST /booking-mandates      -> signed booking mandate
  POST /verify-booking        -> booking verdict
  POST /reservation-mandates  -> signed reservation mandate
  POST /verify-reservation    -> reservation verdict

Every verify response carries {verdict, corrections[], max_attempts,
record_id, verdict_token, ...}. A corrected resubmission is a new
verify call against the same mandate with previous_record_id set to
the earlier check's record_id.
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

DEFAULT_BASE_URL = "https://api.provecart.com"


class ProveCartError(RuntimeError):
    """Raised when the ProveCart API returns a non-200 status."""


class ProveCartClient:
    """Client for the ProveCart verification API.

    Parameters:
        api_key: integrator API key, sent as the X-API-Key header.
        base_url: API base URL (default https://api.provecart.com).
        transport: optional callable ``(path, body) -> (status, dict)``
            replacing the HTTP layer. Intended for offline tests and
            rehearsal runs; when supplied, no network call is made.
        timeout: HTTP timeout in seconds for the default transport.
    """

    def __init__(self, api_key, base_url=DEFAULT_BASE_URL,
                 transport=None, timeout=20):
        self.api_key = api_key
        self.base = base_url.rstrip("/")
        self._transport = transport
        self.timeout = timeout

    # -- transport ---------------------------------------------------
    def _post(self, path, body, extra_headers=None):
        if self._transport is not None:
            return self._transport(path, body)
        headers = {"Content-Type": "application/json",
                   "X-API-Key": self.api_key}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            method="POST",
            headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {}

    def _post_ok(self, path, body, what, idempotency_key=None):
        extra = ({"Idempotency-Key": idempotency_key}
                 if idempotency_key else None)
        status, out = self._post(path, body, extra_headers=extra) \
            if extra else self._post(path, body)
        if status != 200:
            raise ProveCartError(f"{what} failed: {status} {out}")
        return out

    # -- mandate creation ---------------------------------------------
    def create_mandate(self, **fields):
        """Create a signed cart mandate: POST /mandates.

        Required fields include user_id, item_description, category,
        max_total_price and expires_at; item_keywords, currency,
        max_quantity, merchant_allowlist/blocklist, brand and
        variant_constraints are also accepted. Returns the signed
        mandate dict; use its "id" as mandate_id.
        """
        return self._post_ok("/mandates", fields, "mandate creation")

    # Backwards-compatible alias: the cart mandate is the original kind.
    create_cart_mandate = create_mandate

    def create_booking_mandate(self, **fields):
        """Create a signed booking mandate: POST /booking-mandates.

        Required fields include user_id, travelers, origin,
        destination, departure_date, max_total_price and expires_at.
        Returns the signed mandate dict; use its "id".
        """
        return self._post_ok("/booking-mandates", fields,
                             "booking mandate creation")

    def create_reservation_mandate(self, **fields):
        """Create a signed reservation mandate:
        POST /reservation-mandates.

        Required fields include user_id, service_description, date,
        time, party_size, name_on_reservation, max_total_price and
        expires_at. Returns the signed mandate dict; use its "id".
        """
        return self._post_ok("/reservation-mandates", fields,
                             "reservation mandate creation")

    # -- verification ---------------------------------------------------
    def verify_cart(self, mandate_id, merchant, items, total_price,
                    currency="USD", tax=0.0, shipping=0.0, fees=0.0,
                    previous_record_id=None, cart_changed=False,
                    idempotency_key=None):
        """Verify a cart: POST /verify. Returns the verdict dict."""
        body = {"mandate_id": mandate_id, "merchant": merchant,
                "items": items, "total_price": total_price,
                "currency": currency, "tax": tax, "shipping": shipping,
                "fees": fees, "cart_changed": cart_changed}
        if previous_record_id:
            body["previous_record_id"] = previous_record_id
        return self._post_ok("/verify", body, "verify",
                             idempotency_key=idempotency_key)

    def verify_booking(self, mandate_id, merchant, price,
                       travelers=None, legs=None, stays=None, fare=None,
                       currency="USD", previous_record_id=None,
                       booking_changed=False, idempotency_key=None):
        """Verify a booking: POST /verify-booking.

        ``price`` is a dict with at least {"total": ...}; ``legs``
        items carry from_airport, to_airport, depart_at, arrive_at;
        ``travelers`` is a list of traveler names. Returns the
        verdict dict.
        """
        body = {"mandate_id": mandate_id, "merchant": merchant,
                "price": price, "currency": currency,
                "booking_changed": booking_changed}
        if travelers is not None:
            body["travelers"] = travelers
        if legs is not None:
            body["legs"] = legs
        if stays is not None:
            body["stays"] = stays
        if fare is not None:
            body["fare"] = fare
        if previous_record_id:
            body["previous_record_id"] = previous_record_id
        return self._post_ok("/verify-booking", body, "verify-booking",
                             idempotency_key=idempotency_key)

    def verify_reservation(self, mandate_id, merchant, date, time,
                           party_size, name_on_reservation, total_amount,
                           provider_name=None, location=None,
                           deposit_amount=0.0, currency="USD",
                           cancellation=None, previous_record_id=None,
                           reservation_changed=False,
                           idempotency_key=None):
        """Verify a reservation: POST /verify-reservation.
        Returns the verdict dict."""
        body = {"mandate_id": mandate_id, "merchant": merchant,
                "date": date, "time": time, "party_size": party_size,
                "name_on_reservation": name_on_reservation,
                "deposit_amount": deposit_amount,
                "total_amount": total_amount, "currency": currency,
                "reservation_changed": reservation_changed}
        if provider_name is not None:
            body["provider_name"] = provider_name
        if location is not None:
            body["location"] = location
        if cancellation is not None:
            body["cancellation"] = cancellation
        if previous_record_id:
            body["previous_record_id"] = previous_record_id
        return self._post_ok("/verify-reservation", body,
                             "verify-reservation",
                             idempotency_key=idempotency_key)

    # -- one-call checks: create-or-take a mandate, then verify --------
    def _resolve_mandate_id(self, mandate_id, mandate, creator):
        if mandate is not None:
            created = creator(**mandate)
            return created["id"]
        if not mandate_id:
            raise ValueError(
                "pass mandate_id= or mandate={...} so the check has a "
                "signed instruction to compare against")
        return mandate_id

    def check_cart(self, merchant, items, total_price, *,
                   mandate_id=None, mandate=None, **verify_kwargs):
        """Check a cart, creating the mandate first when ``mandate``
        (a dict of mandate fields) is given instead of ``mandate_id``.
        Returns the verdict response dict."""
        mid = self._resolve_mandate_id(mandate_id, mandate,
                                       self.create_mandate)
        return self.verify_cart(mid, merchant, items, total_price,
                                **verify_kwargs)

    def check_booking(self, merchant, price, *, mandate_id=None,
                      mandate=None, **verify_kwargs):
        """Check a booking, creating the booking mandate first when
        ``mandate`` is given instead of ``mandate_id``.
        Returns the verdict response dict."""
        mid = self._resolve_mandate_id(mandate_id, mandate,
                                       self.create_booking_mandate)
        return self.verify_booking(mid, merchant, price, **verify_kwargs)

    def check_reservation(self, merchant, date, time, party_size,
                          name_on_reservation, total_amount, *,
                          mandate_id=None, mandate=None, **verify_kwargs):
        """Check a reservation, creating the reservation mandate
        first when ``mandate`` is given instead of ``mandate_id``.
        Returns the verdict response dict."""
        mid = self._resolve_mandate_id(mandate_id, mandate,
                                       self.create_reservation_mandate)
        return self.verify_reservation(
            mid, merchant, date, time, party_size, name_on_reservation,
            total_amount, **verify_kwargs)


# Short alias.
Client = ProveCartClient


def route_verdict(response, attempt=1):
    """Return (decision, detail): decision is 'proceed', 'fix' or
    'escalate'.

    'fix' is returned only when the verdict is BLOCK, every
    correction is a known action, no correction is marked
    non-correctable, and the retry budget (max_attempts) has not
    been spent. A fix never widens the buyer's authorization: apply
    only the listed corrections, then resubmit carrying the
    response's record_id as previous_record_id. Anything else —
    REVIEW, an unknown verdict, an unknown action — escalates to
    the buyer.
    """
    verdict = response.get("verdict")
    if verdict == "MATCH":
        return "proceed", {"record_id": response.get("record_id")}
    if verdict == "BLOCK":
        corrections = response.get("corrections") or []
        max_attempts = response.get("max_attempts")
        budget_ok = max_attempts is None or attempt < max_attempts
        usable = (
            bool(corrections)
            and all(c.get("action") in KNOWN_ACTIONS for c in corrections)
            and all(c.get("correctable", True) for c in corrections)
        )
        if usable and budget_ok:
            return "fix", {"corrections": corrections,
                           "record_id": response.get("record_id"),
                           "max_attempts": max_attempts}
        reason = "BLOCK without usable corrections"
        if usable and not budget_ok:
            reason = "BLOCK retry budget (max_attempts) spent"
        return "escalate", {"reason": reason,
                            "record_id": response.get("record_id")}
    return "escalate", {"reason": f"verdict {verdict} needs the buyer",
                        "record_id": response.get("record_id")}
