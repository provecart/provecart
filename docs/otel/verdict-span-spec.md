# ProveCart verdict spans — OpenTelemetry specification

**Version:** 1.0 (2026-11-04) · **Status:** published specification +
reference example · **Scope:** any service that calls the ProveCart
pre-payment check and wants distributed tracing around it.

ProveCart compares what a customer asked their AI agent to order,
book, or reserve against what the agent actually built, and returns a
signed **MATCH / REVIEW / BLOCK** verdict before the payment is
captured. This document defines the one span an integrating service
emits around that check, so the check is visible in traces without
the trace ever carrying the transaction itself.

## The span

| Field | Value |
|---|---|
| Span name | `provecart.verify` |
| Kind | `CLIENT` |
| Parent | the caller's checkout / booking / reservation span |
| Status | `OK` when a verdict was returned (any of MATCH, REVIEW, BLOCK — a BLOCK is a successful check, not a span error); `ERROR` only when the check call itself failed (transport error, timeout, malformed response) |

One span per check call. A corrected resubmission after a REVIEW or
BLOCK is a new check call and gets its own span, linked to the first
through the record identifiers below — never by editing the first
span.

## Attributes — the complete, closed list

Exactly five attributes are permitted. All are low-cardinality or
opaque identifiers; none can reconstruct the transaction.

| Attribute | Type | Meaning |
|---|---|---|
| `provecart.record_id` | string | The sealed evidence record id returned by the check. Opaque. |
| `provecart.verdict` | string | `MATCH`, `REVIEW`, or `BLOCK`. |
| `provecart.mandate_kind` | string | `cart`, `booking`, or `reservation`. The *kind* of mandate — never its content. |
| `provecart.correction_count` | int | How many machine-readable corrections the verdict carried (0 on a clean MATCH). A count, never the corrections themselves. |
| `provecart.spec_version` | string | The correction-format spec version the response conforms to (for example `acf-0.1`). |

## Redaction rule (normative)

**A `provecart.verify` span MUST NOT carry intent content.** That
means, without exception:

- no customer instruction text, in whole or in part;
- no item, product, flight, property, or guest names;
- no prices, totals, ceilings, currencies amounts, or quantities;
- no merchant names or domains;
- no dates, times, party sizes, or traveller details;
- no mandate body, cart body, request body, or response body;
- no names, emails, or other personal data of any party.

If a value is not one of the five attributes in the table above, it
does not go on the span — not as an attribute, not as an event, not
in the span name, and not in a link. Debugging a specific check is
done through the sealed evidence record, reached by
`provecart.record_id` inside the checker's own access-controlled
surfaces, never through the trace backend.

Rationale: traces are routinely shipped to third-party backends,
sampled, retained, and seen by people and systems with no need to
know what a customer bought. Identifiers and outcomes are enough to
measure latency, verdict mix, and correction rates; content is not
needed for any of those, so content is excluded by construction.

## What this enables

- Verdict mix and correction-rate dashboards per service, from
  `provecart.verdict` and `provecart.correction_count` alone.
- Latency of the check inside the checkout path, from span duration.
- End-to-end lookup of one check: trace → `provecart.record_id` →
  sealed record (in the checker's own system, under its own access
  rules).

## Conformance

An integration conforms when (1) every check call emits exactly one
`provecart.verify` span, (2) the span carries only attributes from
the closed list, and (3) the redaction rule holds for attributes,
events, links, and the span name. The reference example in
`examples/otel/` implements all three and is the test: run it and
inspect the emitted span — the attribute set printed is the whole
story the trace is allowed to tell.

*ProveCart is built in the Bay Area. Patent pending.*
