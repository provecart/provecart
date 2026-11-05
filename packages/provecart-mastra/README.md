# provecart-mastra

A pre-action hook for Mastra agents, from ProveCart.

> **Status: staged, not yet published.** This package is complete
> and tested offline, and its source lives in the ProveCart flagship
> repository under `packages/provecart-mastra/`. It is **not on npm
> yet** — publication is pending the npm account, which does not
> exist yet. Until then, use it from source (below). This note will
> be replaced with the install command when the package is live.

An agent that buys for someone needs one check in the right place:
after it has built the order, and before any money moves. This
package wraps a Mastra purchase tool so that check runs first,
every time the tool is called. The wrapper reads the pending order,
booking or reservation out of the tool input, compares it with the
customer's signed mandate, and only then decides whether the
wrapped tool executes.

## How it works

ProveCart returns one of three verdicts:

- **MATCH** — the wrapped tool's `execute` runs and its result is
  returned as normal.
- **BLOCK** — the wrapped tool does not run. The wrapper returns a
  refusal object carrying the verdict, the record id and the
  corrections, so the agent can apply a fix that stays inside the
  customer's existing authorization and check again.
- **REVIEW** — the wrapped tool does not run, and the refusal
  object tells the agent to stop and ask the customer. A review is
  never turned into a guess.

A check that fails, a verdict that is not recognized, and a BLOCK
whose corrections use an unknown action all escalate the same way.
Nothing falls through to the purchase tool by accident.

## Use it

With a real Mastra tool built by `createTool`:

```ts
import { createTool } from "@mastra/core/tools";
import { wrapMastraTool } from "provecart-mastra";

const placeOrder = createTool({ id: "place_order", /* ... */ });

const guardedPlaceOrder = wrapMastraTool(placeOrder, {
  client: myProveCartClient,   // injected, see below
  kind: "cart",                // "cart" | "booking" | "reservation"
});
```

The wrapper keeps the tool's id, description and schemas and only
adds the check ahead of `execute`, so it drops into an agent's tool
map in place of the original. For a plain function instead of a
tool object, `withProveCartCheck(execute, options)` does the same
job one level down.

From source, while the npm listing is pending:

```bash
git clone https://github.com/provecart/provecart
# use packages/provecart-mastra, then:
npm install && npm run build && npm test
```

## The client is yours to inject

This package does not hard-wire an HTTP client. Pass any object
with these methods, each resolving to an object with `verdict`,
`corrections`, `record_id` and `max_attempts`:

- `check_cart(payload)`
- `check_booking(payload)`
- `check_reservation(payload)`

If that object also provides
`route_verdict(response) -> (decision, detail)` (a tuple or an
object), with decision one of `proceed`, `fix` or `escalate`, the
wrapper uses it. Otherwise the routing built into this package
applies: MATCH proceeds; BLOCK becomes `fix` only when every
correction is a known action; BLOCK without usable corrections,
REVIEW and anything unknown escalate. A client exposing only
`verify_cart` is adapted for cart checks.

Payloads are taken from the tool input as-is, or from a nested
`cart` / `booking` / `reservation` object when the tool wraps its
order that way. Pass an `extractor(kind, input)` function in the
options if your tools shape their input differently.

## Offline example and test

```bash
npm run build
node examples/mock-example.mjs   # MOCK mode, injected fake client
npm test                         # builds, then runs the smoke test
```

The example and the smoke test run fully offline with a fake
client and a hand-rolled harness — no framework, no network, no
keys. Live use is an explicit opt-in: build your real client and
inject it, as the example marks.

## Notes

Package name: `provecart-mastra` (unscoped; the scoped form was not
used because there is no npm organization behind it yet).

Published by ProveCart, a verification service for agent commerce
based in the Bay Area. Patent pending.

Docs: https://provecart.com/portal/docs ·
Source: https://github.com/provecart/provecart/tree/main/packages/provecart-mastra
