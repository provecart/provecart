# OpenTelemetry: tracing the ProveCart check

ProveCart checks an AI agent's order, booking, or reservation
against what the customer asked for, before the payment is captured,
and returns a signed MATCH / REVIEW / BLOCK verdict with a sealed
evidence record.

If your service calls that check, this folder tells you how to make
the call visible in your traces — safely.

- **Specification:** [verdict-span-spec.md](verdict-span-spec.md) —
  one span named `provecart.verify` per check call, with a closed
  list of five attributes (record id, verdict, mandate kind,
  correction count, spec version) and a normative redaction rule:
  no intent content, no item names, no prices, ever, on the span.
- **Working example:** [`examples/otel/`](../examples/otel/) — a
  small, offline Python snippet using `opentelemetry-api` with a
  stubbed (mock mode) check call. It emits the span to an in-memory
  exporter, prints it, and asserts the attribute set matches the
  spec exactly.

Why so strict? Traces leave your building. Identifiers and outcomes
are enough to measure latency, verdict mix, and correction rates;
the transaction itself belongs in the sealed evidence record,
reached by record id under the checker's own access rules — never
in a trace backend.

*ProveCart is built in the Bay Area. Patent pending.*
