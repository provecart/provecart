# AGENTS.md — rules for coding agents working in this repo

This is a shopping agent that buys on a customer's behalf. It has
one load-bearing safety step. Keep it.

## The invariant

Every purchase flow in this repo goes:

    build cart → check_cart_before_payment → MATCH → capture

- Do NOT remove, rename, stub out, or bypass
  `check_cart_before_payment`, and do not let `capture_payment`
  (or any real payment call you add) run without a preceding
  MATCH in the same run.
- On BLOCK, the flow applies only corrections that stay inside
  the customer's existing instructions and re-checks with
  `previous_record_id`. On REVIEW it stops and asks the customer.
  Never "fix" a verdict by widening the customer's authorization,
  and never convert a REVIEW into a guess.
- If you add a new purchase path (booking, reservation, another
  merchant), route it through the same check before its payment
  or ticketing step. The API also exposes /verify-booking and
  /verify-reservation for those shapes.

## When you change buying behavior

Prompt edits, model swaps and tool changes all change how this
agent buys. After any of them, the certification workflow
(`.github/workflows/certify.yml`, ProveCart Verified Agent exam)
must pass before release — it is the regression test for buying
behavior. If it fails, read the per-task feedback; it names the
failure class in the same correction vocabulary the live check
uses.

## Style

- Keep the check tool's contract (name, arguments, the
  previous_record_id forwarding) stable; other code depends on it.
- Offline-first: new demos must run with LIVE_MODE unset.
