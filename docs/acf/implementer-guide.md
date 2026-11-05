# ACF v0.1 — Implementer guide

How to produce and consume the Agent Correction Format (ACF) v0.1.
Companion to the spec (https://provecart.com/standards/correction-format),
the worked examples (`worked-examples.md`), and the conformance
vectors (`test-vectors.json`). This guide is operational, not
normative: where it and the spec differ, the spec governs.

## For checkers (ACF producers)

Producer checklist — a response is ACF-conformant when all of
these hold:

1. **One verdict object per check**, with `verdict`, `results`,
   `record_id`, and `verdict_token` always present (spec §3).
2. **`corrections` only on REVIEW or BLOCK**, only when at least
   one failing dimension is agent-correctable, and only for
   correctable dimensions (spec §§4–5).
3. **Every correction is self-contained**: `dimension`, `action`
   (from the closed vocabulary, spec §4.1), `reason`, `expected`,
   `actual`, plus `item` or `field` when the correction concerns
   one line item or one subject field.
4. **`expected` comes from the buyer's signed instructions only.**
   Never emit thresholds, scores, match internals, or any value
   the mandate holder did not themselves state.
5. **Non-correctable dimensions are marked, not corrected**: no
   correction entry, and `"correctable": false` on the dimension's
   result — so agents do not burn their retry budget on failures
   no edit can fix (expired/unsigned instruction reference,
   excluded merchant, exhausted standing budget, checker-side
   error).
6. **Verify the instruction signature before checking.** A failed
   verification is itself the non-correctable `mandate_signature`
   dimension.
7. **Seal before you answer.** The check is written to the
   tamper-evident, hash-chained evidence log before the verdict
   is relied on; `record_id` in the response is the pointer
   (spec §8).
8. **Verdict tokens are single-use and hold-bound.** One token
   authorizes at most one capture or issuance, against exactly
   the record, mandate, and subject hash it was issued for —
   checked against the hold record, never against values
   re-supplied in the action request. A corrected subject gets a
   new record and a new token.
9. **`max_attempts` is stated** whenever corrections are emitted
   (reference value 3). It is a suggested budget, not a verdict.
10. **Fail safe.** A checker-side failure returns REVIEW with the
    `engine_error` dimension, never a silent MATCH, and is sealed
    like every other check.

## For agents and frameworks (ACF consumers)

Consumer checklist:

1. **Read `corrections` before escalating.** A REVIEW or BLOCK
   with corrections is a work order, not a dead end.
2. **Apply only what restores conformity.** Auto-apply a
   correction when the edited subject conforms to the signed
   instructions exactly as given. Nothing else is auto-applicable
   (see the escalation rule below).
3. **Resubmit as a new check** against the same instruction
   reference, carrying `previous_record_id` from the attempt
   being superseded. Never edit a past verdict; the attempt chain
   is the evidence.
4. **Respect the budget.** Stop at `max_attempts` and escalate.
   Retrying a dimension marked `"correctable": false` is always
   wrong — escalate immediately instead.
5. **Ignore actions you do not recognize.** Minor versions may
   add actions; an unrecognized action makes that correction
   not-auto-applicable, never an error.
6. **Do not require a per-correction `severity` field.** In v0.1
   severity is structural: the dimension's `status`
   (`soft_fail`/`hard_fail`) under the overall verdict.
7. **Carry the pointer.** Keep `record_id` with the order,
   booking, or reservation it decided, so the evidence chain can
   be produced later (dispute, refund, audit).

## The retry budget

- The checker suggests a budget in `max_attempts` (reference: 3).
- Each resubmission is a fresh check with a fresh record; attempts
  are counted by the chain of `previous_record_id` /
  `supersedes` links.
- Exhausting the budget is not a verdict and not a failure of the
  format: the agent stops editing and escalates with the full
  chain attached.

## The buyer-escalation rule

An agent may auto-apply **only** corrections that bring the
subject *into* conformity with the signed instruction reference.
Any change that would go beyond what the buyer authorized —
paying above the ceiling, accepting a materially different
product, traveler, date, or terms — is never an auto-fix:

- the checker returns REVIEW for it, and
- the agent must ask the buyer and proceed only with a fresh
  instruction reference or the buyer's explicit approval.

Corrections that *restore* a name, date, time, item, or total to
the instructed value are in-conformity fixes and may be applied
without asking. Corrections that would *change* the instruction
itself are buyer decisions, always.

## Versioning policy

- **The version stamp** (what "current" means): the canonical
  page https://provecart.com/standards/correction-format always
  serves the current version of the spec. Each version is also
  published as an immutable file (`agent-correction-format-vX.Y.md`
  / `.pdf`) beside it; an immutable file never changes after
  publication. "Current" = the highest version whose status line
  reads *current*; earlier versions remain available and are
  marked *superseded*.
- **Minor versions (v0.2, v0.3, …)** may: add actions to the
  vocabulary, add optional fields, clarify wording. They may not:
  remove or rename actions or fields, change verdict semantics,
  or change the retry/escalation rules. Consumers written against
  v0.1 keep working under any v0.x.
- **Major versions (v1.0, v2.0)** are required for anything in
  the "may not" list. A major version is a new immutable file and
  a new canonical-page state; the change is announced in the
  changelog with a migration note.
- **How a v0.2 gets proposed**: anyone may propose a change —
  an issue or pull request against the spec in the ProveCart
  repo (github.com/provecart/provecart, `docs/`), or a comment
  in the standards discussion where ACF was filed (the UCP
  verification-extension thread). ProveCart, as editor of the
  v0.x line, accepts, declines, or defers each proposal in the
  open, with reasons, and records the outcome in the changelog.
  A proposal backed by a second independent implementation
  carries the most weight; a proposal that only renames things
  carries the least.
- **Errata** (a fix that changes no normative content — a cut-off
  sentence, a broken reference) are applied to the current
  version, recorded in the changelog with the date, and do not
  change the version number.

## Conformance, quickly

Run `test-vectors.json` against your implementation: 15 vectors
(6 cart, 4 booking, 5 reservation), covering MATCH, single- and
multi-correction BLOCKs, REVIEWs, and both non-correctable
shapes. A vector passes when the verdict matches exactly and the
set of `(dimension, action)` correction pairs matches exactly.
Then compare your live responses against `worked-examples.md` —
four complete, unelided checks, including the sealed-record
fetch.
