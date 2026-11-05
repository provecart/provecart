# Standalone reference checker — ACF v0.2, no service required

A small, dependency-free implementation of the **Agent Correction
Format (ACF) v0.2** — the conformity-corrections format published
at https://provecart.com/standards/correction-format (schema:
https://provecart.com/standards/acf-v0.2.schema.json) — written
from the specification document, the JSON Schema and the shipped
conformance fixtures alone. It never calls the ProveCart API or
any other service.

Give it two JSON documents — a buyer's signed instruction (the
mandate shapes the published fixtures use) and a built checkout
subject (cart, booking or reservation) — and it emits the v0.2
checkout fragment: the host's `messages[]` entries carrying
`com.provecart.conformity.*` codes with `expected` / `actual` /
`action` extension fields, plus the one namespaced conformity
object with the verdict and its bindings.

## Run it

```sh
# one check
python3 checker.py scenarios/f02-cart-block-price-quantity-item.instruction.json \
                   scenarios/f02-cart-block-price-quantity-item.subject.json

# the consumer half: what a platform does with a checker's output
python3 checker.py decide FRAGMENT.json

# the full fixture battery (the one command that proves this package)
python3 test_checker.py
```

Python 3 standard library only. `test_checker.py` additionally
uses `jsonschema` when it is installed (as the spec package's own
validator does) and falls back to structural validation when it
is not.

## What it proves

The format's central claim is that conformance needs nothing from
its publisher: no API account, no scoreboard entry, no credential
(spec Section 12). This package is the executable form of that
claim. Running `test_checker.py` reproduces, from the document
alone, the verdict and the machine-actionable content of every
shipped conformance fixture — the same fixtures generated from the
reference implementation's production code paths:

| Fixture | Scenario | Verdict reproduced |
|---|---|---|
| f01 | conforming cart | MATCH |
| f02 | over ceiling + over quantity + indeterminate item | BLOCK, 3 corrections |
| f03 | indeterminate item only | REVIEW |
| f04 | booking one day off the mandated date | BLOCK, `change_travel_date` |
| f05 | f04 repaired and resubmitted, chain-linked | MATCH |
| f06 | reservation 30 min out against a 15-min tolerance | BLOCK, `change_time` |
| f07 | blocklisted merchant | BLOCK, non-correctable, no correction emitted |
| f08 | unknown code + unknown action (consumer behavior) | consumer escalates, auto-applies nothing |

143 checks, all passing; the captured run is in
`test-output.txt`. The comparison is exact on everything the spec
makes normative — verdict, codes, severities, JSONPaths, and every
extension field including which fields are absent — and validates
every emitted message and object against the published JSON
Schema. Two things are deliberately **not** compared, and the test
docstring says why: `content` wording (each implementation renders
its own sentences; the structured fields govern) and the
projections' record-id/digest values (the reference service's ids
are random UUIDs over its stored artifacts; this checker derives
its own deterministically from the two documents it was given —
which is also how it demonstrates the spec's idempotency anchor
offline: same inputs, same record id, every run).

One documented delta: the shipped f05 projection shows
`previous_record_id` as null because the fixture capture pipeline
elided the field. This checker carries the chain link, as spec
Sections 4 and 7 require; the test feeds it this checker's own
f04 record id, mirroring the flow the fixture generator used.

## Honest label

This is **ProveCart-authored reference code for the format
ProveCart publishes** — the "second implementation" seed, not an
independent implementation. An independent implementation is one
written by a party with no stake in the format; nothing here is
described as that, and the spec's own known-limitations section
says the same about the format's adoption state. What this
package establishes is narrower and real: the document, schema
and fixtures are sufficient to build a conforming checker, and
here is one, passing the fixtures.

## What it is not

- **Not an authorization.** It emits no `verdict_token` and no
  `evidence_url`. A verdict presented to authorize a payment
  capture or ticket issuance must come from an engaged checker
  that seals an evidence record and issues a single-use,
  hold-bound token (spec Section 4). Never present this
  checker's output as one.
- **Not the comparison the service runs.** The spec defines the
  reporting shape, not the comparison. This implementation's
  comparison rules are the weakest honest ones that reproduce
  the fixtures — keyword coverage for item conformity, exact
  airport endpoints (the outbound destination is the first
  leg's arrival; a round trip's flight home is not the
  destination), stated tolerances taken literally — and each is
  documented in `checker.py`'s module notes. A production
  checker with catalog and schedule access should do better;
  the format does not change.
- **Not complete coverage of the vocabulary.** Standing-budget
  accounting needs check history and is out of scope offline.
  Signature verification runs only when the instruction carries
  a `signature` and `--secret` is supplied (HMAC-SHA256 over
  the canonical instruction).
- **Fail-safe by construction.** Any internal error produces an
  `engine_error` REVIEW fragment, never a pass (spec Section
  5.5). The consumer half refuses expired verdicts, escalates
  REVIEW, unknown codes, unknown actions, non-correctable
  failures and anything requiring buyer approval, and never
  partially applies a repair plan around an escalation.

A note on the `decide` example: it evaluates expiry against the
current time, so the frozen f08 capture (issued 2026-11-05)
correctly reads as expired today; the battery pins f08's
in-window behavior with an explicit clock.

## Files

| File | What it is |
|---|---|
| `checker.py` | The checker (emitter) and the consumer decision function. Stdlib only. |
| `test_checker.py` | The fixture battery described above. |
| `test-output.txt` | Captured full run: 143 PASS, 0 FAIL. |
| `scenarios/` | The instruction/subject pairs for f01–f07, reconstructed from the spec package's published fixture generator (`standards/generate_fixtures.py`). All parties and items synthetic. |

## License

This package may be copied and shared freely, with attribution
to ProveCart. The format it implements is free to implement:
ProveCart commits that any patent claim it owns or controls that
is *necessarily infringed* by implementing the format as
published — an essential claim — is licensed **royalty-free** to
anyone, for the purpose of implementing the format (a RAND-Z
style commitment; spec Section 16). The commitment covers the
format only; it does not license ProveCart's verification
service, checker, certification exam, evidence store, or brand.
