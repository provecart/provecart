# ProveCart x Stagehand: check before checkout

A Stagehand browser agent that cannot buy the wrong thing: before
the buy click, it sends its cart to ProveCart, which compares the
cart against the buyer's signed mandate and answers MATCH, BLOCK
(with machine-readable corrections), or REVIEW.

Built by ProveCart (Bay Area). ProveCart is a neutral verification
API for agent commerce: it checks what an agent actually built —
cart, booking, or reservation — against what the buyer actually
authorized, before payment is captured.

## The interlock

```
build cart -> checkBeforeCheckout -> MATCH -> click buy
```

`src/checkBeforeCheckout.ts` is the whole pattern, and it is small
on purpose — copy it into your own agent:

- **MATCH** → the buy click runs. It runs at most once, and only
  after a MATCH in the same run.
- **BLOCK** → the flow applies *only* the corrections ProveCart
  returns (each one brings the cart back *into* the buyer's
  existing authorization — a different size, a lower quantity),
  then re-checks with `previous_record_id` set to the blocked
  check's record, inside the returned `max_attempts` budget.
- **REVIEW** → the flow stops and asks the buyer. It never guesses,
  and it never widens the buyer's authorization to force a pass.
  A BLOCK whose corrections contain an unknown action escalates
  the same way.

Browser agents misclick: the classic failure is the wrong size or
date selected at checkout, discovered after the order lands. This
example's `fix` scenario is exactly that — the agent selects
US 9, the buyer authorized US 10, ProveCart blocks with a
`change_variant` correction, the agent fixes the page, re-checks,
matches, and only then buys.

## Run it (offline, default)

No keys, no account, no network beyond 127.0.0.1. The demo store
is a local page (`demo/demo-store.html`); verdicts come from a
local fake verdict server (`src/mockProveCart.ts`) that implements
the same wire contract as the real API.

```bash
npm install
npm run smoke        # all three verdict paths, asserted
npm start -- match   # agent buys exactly what was authorized
npm start -- fix     # wrong size -> BLOCK -> fix -> MATCH -> buy
npm start -- review  # extra item -> REVIEW -> halt, no buy click
```

Smoke output (real run):

```
PASS match : MATCH on check #1, buy clicked exactly once
PASS fix   : BLOCK -> change_variant US 9->US 10 -> re-check (previous_record_id=rec_mock_2) -> MATCH, buy clicked once
PASS review: REVIEW -> halted, buy clicks = 0, escalated ("verdict REVIEW needs the buyer")
PASS guard : BLOCK with unknown correction action -> escalate, never applied
SMOKE OK: 4/4 paths behave (match, block->fix->match, review->halt, unknown-action guard)
```

## Live modes (explicit opt-in)

```bash
# Real ProveCart checks (the demo cart is still local; nothing is bought):
PROVECART_LIVE=1 PROVECART_API_KEY=... npm start -- fix

# A real Stagehand session driving the local demo page
# (needs an LLM provider key; add BROWSERBASE_API_KEY to run on
# Browserbase cloud browsers instead of a local browser):
STAGEHAND_LIVE=1 npm start -- fix
```

Without those variables, nothing leaves the machine and no real
merchant is ever contacted.

## Layout

| File | What it is |
| --- | --- |
| `src/checkBeforeCheckout.ts` | The reusable interlock (the part to copy) |
| `src/provecart.ts` | Vendored ProveCart client + verdict routing, ported from the reference client (ACF v0.2 semantics) |
| `src/drivers.ts` | Simulated offline driver + real Stagehand v3 driver |
| `src/mockProveCart.ts` | Local fake verdict server (127.0.0.1 only) |
| `src/index.ts` | The three demo scenarios and the mandate |
| `demo/demo-store.html` | The local demo store page |
| `test/smoke.ts` | Offline smoke test over real local HTTP |

## Notes

- `src/provecart.ts` is vendored so the example is self-contained.
  A packaged ProveCart client is published separately; swapping it
  in means deleting that file and importing the package — the
  interlock's contract (`verifyCart` + `routeVerdict`) stays the
  same.
- The mandate in `src/index.ts` authorizes one pair of Trail
  Runner Shoes, size US 10, up to a stated total. Try changing the
  mandate or the agent's choices and watch the verdicts move.
- Bookings and reservations follow the same shape through the
  API's `/verify-booking` and `/verify-reservation` routes.

MIT licensed.
