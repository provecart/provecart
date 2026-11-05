# provecart-adk

A pre-action hook for Google ADK agents, from ProveCart.

An agent that buys for someone needs one check in the right place:
after it has built the order, and before any money moves. This
package puts that check on ADK's tool boundary. When a purchase
tool is about to run, the hook reads the pending order, booking or
reservation out of the tool arguments, compares it with the
customer's signed mandate, and only then decides whether the tool
call goes ahead.

```bash
pip install provecart-adk
pip install "provecart-adk[adk]"   # also installs google-adk
```

## How it works

ProveCart returns one of three verdicts:

- **MATCH** — the tool runs. The callback returns `None`, which is
  ADK's signal to proceed as normal.
- **BLOCK** — the tool does not run. ADK's documented refusal path
  applies: a `before_tool_callback` that returns a dict skips the
  tool call and that dict becomes the tool result. The dict carries
  the verdict, the record id and the corrections, so the agent can
  apply a fix that stays inside the customer's existing
  authorization and check again.
- **REVIEW** — the tool does not run, and the refusal dict tells
  the agent to stop and ask the customer. A review is never turned
  into a guess.

A check that fails, a verdict that is not recognized, and a BLOCK
whose corrections use an unknown action all escalate the same way.
Nothing falls through to the purchase tool by accident.

## Use it two ways

As an agent callback:

```python
from provecart_adk import ProveCartGuard, make_before_tool_callback

guard = ProveCartGuard(client=my_provecart_client)
agent = LlmAgent(
    name="shopper",
    tools=[place_order],
    before_tool_callback=make_before_tool_callback(guard),
)
```

Or as a plugin, registered once so it covers every agent and tool
in the app:

```python
from provecart_adk import ProveCartPlugin

plugin = ProveCartPlugin(client=my_provecart_client)
# Runner(..., plugins=[plugin]) or App(..., plugins=[plugin])
```

## The client is yours to inject

This package does not hard-wire an HTTP client. Pass any object
with these methods, each returning a dict with `verdict`,
`corrections`, `record_id` and `max_attempts`:

- `check_cart(**payload)`
- `check_booking(**payload)`
- `check_reservation(**payload)`

If that object also provides
`route_verdict(response) -> (decision, detail)`, with decision one
of `proceed`, `fix` or `escalate`, the hook uses it. Otherwise the
routing built into this package applies: MATCH proceeds; BLOCK
becomes `fix` only when every correction is a known action; BLOCK
without usable corrections, REVIEW and anything unknown escalate.
A client exposing only `verify_cart` is adapted for cart checks.

## Which tools are watched

By default the guard watches common purchase names — `place_order`,
`checkout`, `capture_payment` and friends for carts; `book_flight`,
`create_booking` for bookings; `make_reservation`, `reserve_table`
for reservations — and ignores every other tool without calling the
client. Pass your own map to watch exactly your tool names:

```python
guard = ProveCartGuard(
    client=my_provecart_client,
    tool_kinds={"submit_payment": "cart", "hold_room": "booking"},
)
```

Payloads are taken from the tool arguments as-is, or from a nested
`cart` / `booking` / `reservation` dict when the tool wraps its
order that way. Pass an `extractor(kind, args) -> dict` callable if
your tools shape their arguments differently.

## Offline example and tests

```bash
python examples/mock_example.py   # MOCK mode, injected fake client
python -m pytest tests/ -q        # offline; ADK is stubbed if absent
```

The example defaults to mock mode and makes no network calls on
import or on a normal run. Live use is an explicit opt-in: build
your real client and inject it, as the example marks.

## Notes

Published by ProveCart, a verification service for agent commerce
based in the Bay Area. Patent pending.

Docs: https://provecart.com/portal/docs ·
Source: https://github.com/provecart/provecart/tree/main/packages/provecart-adk
