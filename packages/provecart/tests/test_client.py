"""Offline unit tests for the provecart client.

A stub transport replaces the HTTP layer: no network, no live calls.
Covers MATCH / BLOCK-fix / REVIEW routing and previous_record_id
chaining for carts, bookings, and reservations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from provecart import ProveCartClient, route_verdict  # noqa: E402


class StubTransport:
    """Records every (path, body) call and replays queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, path, body):
        self.calls.append((path, dict(body)))
        return self.responses.pop(0)


def mandate_ok(mid="m-1"):
    return (200, {"id": mid, "signature": "sig"})


MERCHANT = {"name": "Example Shop", "domain": "shop.example.com"}
CART_MANDATE = {
    "user_id": "user-123",
    "item_description": "Wireless noise cancelling over-ear headphones",
    "item_keywords": ["wireless", "headphones"],
    "category": "electronics",
    "max_total_price": 300.00,
    "currency": "USD",
    "max_quantity": 1,
    "expires_at": "2027-01-01T00:00:00Z",
}
ITEMS = [{"name": "Wireless Headphones", "variant": "black",
          "quantity": 1, "unit_price": 249.99}]


def test_match_routes_proceed():
    stub = StubTransport([mandate_ok(),
                          (200, {"verdict": "MATCH", "record_id": "r-1"})])
    client = ProveCartClient("test-key", transport=stub)
    out = client.check_cart(MERCHANT, ITEMS, 249.99, mandate=CART_MANDATE)
    assert out["verdict"] == "MATCH"
    assert stub.calls[0][0] == "/mandates"
    assert stub.calls[1][0] == "/verify"
    assert stub.calls[1][1]["mandate_id"] == "m-1"
    decision, detail = route_verdict(out)
    assert decision == "proceed"
    assert detail["record_id"] == "r-1"


def test_check_cart_with_existing_mandate_id_skips_creation():
    stub = StubTransport([(200, {"verdict": "MATCH", "record_id": "r-9"})])
    client = ProveCartClient("test-key", transport=stub)
    out = client.check_cart(MERCHANT, ITEMS, 249.99, mandate_id="m-42")
    assert out["verdict"] == "MATCH"
    assert len(stub.calls) == 1
    assert stub.calls[0][1]["mandate_id"] == "m-42"


def test_block_with_known_corrections_routes_fix():
    resp = {"verdict": "BLOCK", "record_id": "r-2", "max_attempts": 3,
            "corrections": [
                {"action": "change_variant", "dimension": "variant",
                 "expected": "black", "actual": "white"},
                {"action": "reduce_quantity", "dimension": "quantity",
                 "expected": 1, "actual": 2}]}
    decision, detail = route_verdict(resp)
    assert decision == "fix"
    assert detail["record_id"] == "r-2"
    assert detail["max_attempts"] == 3
    assert detail["corrections"] == resp["corrections"]


def test_block_fix_then_resubmit_chains_previous_record_id():
    blocked = (200, {"verdict": "BLOCK", "record_id": "r-2",
                     "max_attempts": 3,
                     "corrections": [{"action": "change_variant"}]})
    matched = (200, {"verdict": "MATCH", "record_id": "r-3"})
    stub = StubTransport([blocked, matched])
    client = ProveCartClient("test-key", transport=stub)
    first = client.verify_cart("m-1", MERCHANT, ITEMS, 249.99)
    decision, detail = route_verdict(first)
    assert decision == "fix"
    fixed = [{"name": "Wireless Headphones", "variant": "black",
              "quantity": 1, "unit_price": 249.99}]
    second = client.verify_cart(
        "m-1", MERCHANT, fixed, 249.99,
        previous_record_id=detail["record_id"], cart_changed=True)
    assert second["verdict"] == "MATCH"
    assert stub.calls[1][1]["previous_record_id"] == "r-2"
    assert stub.calls[1][1]["cart_changed"] is True
    assert "previous_record_id" not in stub.calls[0][1]


def test_review_routes_escalate():
    decision, detail = route_verdict(
        {"verdict": "REVIEW", "record_id": "r-4"})
    assert decision == "escalate"
    assert detail["record_id"] == "r-4"


def test_unknown_verdict_routes_escalate():
    decision, _ = route_verdict({"verdict": "SOMETHING_ELSE"})
    assert decision == "escalate"
    decision, _ = route_verdict({})
    assert decision == "escalate"


def test_block_with_unknown_action_routes_escalate():
    resp = {"verdict": "BLOCK", "record_id": "r-5", "max_attempts": 3,
            "corrections": [{"action": "raise_the_budget"}]}
    decision, _ = route_verdict(resp)
    assert decision == "escalate"


def test_block_without_corrections_routes_escalate():
    decision, _ = route_verdict(
        {"verdict": "BLOCK", "record_id": "r-6", "corrections": []})
    assert decision == "escalate"


def test_block_non_correctable_routes_escalate():
    resp = {"verdict": "BLOCK", "record_id": "r-7", "max_attempts": 3,
            "corrections": [{"action": "remove_item",
                             "correctable": False}]}
    decision, _ = route_verdict(resp)
    assert decision == "escalate"


def test_block_after_budget_spent_routes_escalate():
    resp = {"verdict": "BLOCK", "record_id": "r-8", "max_attempts": 3,
            "corrections": [{"action": "remove_item"}]}
    decision, detail = route_verdict(resp, attempt=3)
    assert decision == "escalate"
    assert "max_attempts" in detail["reason"]


def test_booking_check_creates_mandate_and_verifies():
    stub = StubTransport([mandate_ok("bm-1"),
                          (200, {"verdict": "MATCH", "record_id": "br-1"})])
    client = ProveCartClient("test-key", transport=stub)
    mandate = {
        "user_id": "user-123",
        "travelers": [{"name": "Alex Rivera"}],
        "origin": {"airport": "SFO"},
        "destination": {"airport": "JFK"},
        "departure_date": "2027-03-10",
        "max_total_price": 500.00,
        "expires_at": "2027-03-01T00:00:00Z",
    }
    legs = [{"from_airport": "SFO", "to_airport": "JFK",
             "depart_at": "2027-03-10T08:00:00Z",
             "arrive_at": "2027-03-10T16:30:00Z"}]
    out = client.check_booking(
        MERCHANT, {"total": 412.00}, mandate=mandate,
        travelers=["Alex Rivera"], legs=legs)
    assert out["verdict"] == "MATCH"
    assert stub.calls[0][0] == "/booking-mandates"
    assert stub.calls[1][0] == "/verify-booking"
    assert stub.calls[1][1]["mandate_id"] == "bm-1"
    assert stub.calls[1][1]["price"] == {"total": 412.00}
    decision, _ = route_verdict(out)
    assert decision == "proceed"


def test_booking_resubmit_chains_previous_record_id():
    stub = StubTransport([
        (200, {"verdict": "BLOCK", "record_id": "br-2", "max_attempts": 3,
               "corrections": [{"action": "change_airport"}]}),
        (200, {"verdict": "MATCH", "record_id": "br-3"})])
    client = ProveCartClient("test-key", transport=stub)
    first = client.verify_booking("bm-1", MERCHANT, {"total": 412.00})
    decision, detail = route_verdict(first)
    assert decision == "fix"
    client.verify_booking("bm-1", MERCHANT, {"total": 399.00},
                          previous_record_id=detail["record_id"],
                          booking_changed=True)
    assert stub.calls[1][1]["previous_record_id"] == "br-2"
    assert stub.calls[1][1]["booking_changed"] is True


def test_reservation_check_creates_mandate_and_verifies():
    stub = StubTransport([mandate_ok("rm-1"),
                          (200, {"verdict": "MATCH", "record_id": "rr-1"})])
    client = ProveCartClient("test-key", transport=stub)
    mandate = {
        "user_id": "user-123",
        "service_description": "Dinner reservation for two",
        "date": "2027-03-10", "time": "19:00", "party_size": 2,
        "name_on_reservation": "Alex Rivera",
        "max_total_price": 60.00,
        "expires_at": "2027-03-09T00:00:00Z",
    }
    out = client.check_reservation(
        MERCHANT, "2027-03-10", "19:00", 2, "Alex Rivera", 40.00,
        mandate=mandate)
    assert out["verdict"] == "MATCH"
    assert stub.calls[0][0] == "/reservation-mandates"
    assert stub.calls[1][0] == "/verify-reservation"
    assert stub.calls[1][1]["mandate_id"] == "rm-1"
    assert stub.calls[1][1]["total_amount"] == 40.00


def test_reservation_block_routes_fix_and_chains():
    stub = StubTransport([
        (200, {"verdict": "BLOCK", "record_id": "rr-2", "max_attempts": 3,
               "corrections": [{"action": "change_party_size"}]}),
        (200, {"verdict": "REVIEW", "record_id": "rr-3"})])
    client = ProveCartClient("test-key", transport=stub)
    first = client.verify_reservation(
        "rm-1", MERCHANT, "2027-03-10", "19:00", 4, "Alex Rivera", 40.00)
    decision, detail = route_verdict(first)
    assert decision == "fix"
    second = client.verify_reservation(
        "rm-1", MERCHANT, "2027-03-10", "19:00", 2, "Alex Rivera", 40.00,
        previous_record_id=detail["record_id"], reservation_changed=True)
    assert stub.calls[1][1]["previous_record_id"] == "rr-2"
    decision2, _ = route_verdict(second)
    assert decision2 == "escalate"


def test_create_mandate_helpers_hit_the_three_endpoints():
    stub = StubTransport([mandate_ok("a"), mandate_ok("b"),
                          mandate_ok("c")])
    client = ProveCartClient("test-key", transport=stub)
    assert client.create_mandate(**CART_MANDATE)["id"] == "a"
    assert client.create_booking_mandate(user_id="u")["id"] == "b"
    assert client.create_reservation_mandate(user_id="u")["id"] == "c"
    paths = [c[0] for c in stub.calls]
    assert paths == ["/mandates", "/booking-mandates",
                     "/reservation-mandates"]


def test_api_error_raises():
    stub = StubTransport([(403, {"detail": "bad key"})])
    client = ProveCartClient("test-key", transport=stub)
    try:
        client.create_mandate(**CART_MANDATE)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError on non-200")


def test_check_requires_mandate_or_id():
    client = ProveCartClient("test-key", transport=StubTransport([]))
    try:
        client.check_cart(MERCHANT, ITEMS, 249.99)
    except ValueError:
        return
    raise AssertionError("expected ValueError without a mandate")
