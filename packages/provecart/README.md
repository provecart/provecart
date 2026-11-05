# provecart

Your agent put the wrong variant in the cart — the wrong size, the wrong model, a quantity nobody asked for — and your user paid for it. By the time anyone noticed, the order had shipped, and the return came out of somebody's pocket. That is the failure this package exists to stop: one check, between what the agent built and the payment, that compares the transaction against what the buyer actually said.

ProveCart is a neutral verification API for agent commerce. You record the buyer's instruction as a signed mandate, send what the agent actually built, and get back a signed verdict — `MATCH`, `REVIEW`, or `BLOCK` — before payment is captured (or, for bookings, before a ticket is issued). A `BLOCK` or `REVIEW` answer carries machine-readable corrections, so the agent can fix what it built and resubmit instead of losing the sale or guessing. Every check is written to a sealed evidence record. ProveCart never holds or moves money.

```bash
pip install provecart
```

Standard library only. No dependencies.

## Check a cart

```python
from provecart import ProveCartClient, route_verdict
client = ProveCartClient(api_key="YOUR_API_KEY")
verdict = client.check_cart(merchant={"name": "Example Shop", "domain": "shop.example.com"}, items=[{"name": "Wireless Headphones", "variant": "black", "quantity": 1, "unit_price": 249.99}], total_price=249.99, mandate={"user_id": "user-123", "item_description": "Wireless noise cancelling over-ear headphones", "item_keywords": ["wireless", "headphones"], "category": "electronics", "max_total_price": 300.00, "currency": "USD", "max_quantity": 1, "expires_at": "2027-01-01T00:00:00Z"})
decision, detail = route_verdict(verdict)  # proceed / fix / escalate
```

Already holding a mandate id? Pass `mandate_id=` instead of `mandate=` — `check_cart` takes either. The lower-level pair is also there when you want the steps separate: `create_mandate(**fields)` returns the signed mandate, and `verify_cart(mandate_id, merchant, items, total_price, ...)` runs the check.

## Check a booking

```python
from provecart import ProveCartClient, route_verdict
client = ProveCartClient(api_key="YOUR_API_KEY")
verdict = client.check_booking(merchant={"name": "Example Air", "domain": "air.example.com"}, price={"total": 412.00}, travelers=["Alex Rivera"], legs=[{"from_airport": "SFO", "to_airport": "JFK", "depart_at": "2027-03-10T08:00:00Z", "arrive_at": "2027-03-10T16:30:00Z"}], mandate={"user_id": "user-123", "travelers": [{"name": "Alex Rivera"}], "origin": {"airport": "SFO"}, "destination": {"airport": "JFK"}, "departure_date": "2027-03-10", "max_total_price": 500.00, "currency": "USD", "expires_at": "2027-03-01T00:00:00Z"})
decision, detail = route_verdict(verdict)  # gate both capture and ticket issuance on MATCH
```

The separate steps are `create_booking_mandate(**fields)` and `verify_booking(mandate_id, merchant, price, travelers=..., legs=..., stays=..., fare=...)`.

## Check a reservation

```python
from provecart import ProveCartClient, route_verdict
client = ProveCartClient(api_key="YOUR_API_KEY")
verdict = client.check_reservation(merchant={"name": "Example Table", "domain": "table.example.com"}, date="2027-03-10", time="19:00", party_size=2, name_on_reservation="Alex Rivera", total_amount=40.00, mandate={"user_id": "user-123", "service_description": "Dinner reservation for two", "date": "2027-03-10", "time": "19:00", "party_size": 2, "name_on_reservation": "Alex Rivera", "max_total_price": 60.00, "currency": "USD", "expires_at": "2027-03-09T00:00:00Z"})
decision, detail = route_verdict(verdict)  # proceed / fix / escalate
```

The separate steps are `create_reservation_mandate(**fields)` and `verify_reservation(mandate_id, merchant, date, time, party_size, name_on_reservation, total_amount, ...)`.

## What to do with the verdict

`route_verdict` encodes the consumer rules of the Agent Correction Format, and they are deliberately strict:

- **MATCH → proceed.** Capture the payment (or issue the ticket).
- **BLOCK → fix, narrowly.** Fix only when every correction in the response is a known action that brings the transaction back inside the buyer's existing authorization. Apply exactly those corrections, then resubmit as a new check carrying the earlier check's `record_id` as `previous_record_id`, within the response's `max_attempts` budget.
- **REVIEW, unknown verdict, unknown action → escalate.** Stop and ask the buyer. Never guess, and never widen the buyer's authorization to make a verdict go away.

```python
decision, detail = route_verdict(first_verdict)
if decision == "fix":
    # ... apply detail["corrections"] to the transaction, nothing else ...
    second = client.check_cart(..., mandate_id=same_id, previous_record_id=detail["record_id"])
```

## Offline and mock runs

The client takes an optional `transport` callable, `(path, body) -> (status, dict)`, that replaces the HTTP layer entirely. Point it at canned verdicts and the full mandate → check → route → resubmit loop runs with no network and no API key traffic — that is how this package's own test suite works, and it is the recommended way to rehearse an integration before wiring a real key:

```python
def stub(path, body):
    return 200, {"id": "m-1"} if "mandates" in path else {"verdict": "MATCH", "record_id": "r-1"}
client = ProveCartClient(api_key="test", transport=stub)
```

Calls made with a sandbox key against the live API behave exactly as in production and stay sealed under that key, separate from live data.

## Links

- Agents and certification: https://provecart.com/agents
- Correction format standard: https://provecart.com/standards/correction-format
- API reference: https://api.provecart.com/docs

ProveCart. Prove the cart. Patent pending.
