# Example: emitting the `provecart.verify` span

`verify_span.py` is the reference implementation of the
[verdict-span spec](../docs/otel/verdict-span-spec.md): one
OpenTelemetry span around a ProveCart check call, carrying only
identifiers and outcome.

The check itself is **stubbed (mock mode)** — the example runs fully
offline, with no network, no credentials, and no real transaction.
To use it against a live integration, replace the single
`stubbed_check()` function with your check call and map the same
five response fields; nothing else changes.

## Run it

```sh
pip install opentelemetry-api opentelemetry-sdk
python verify_span.py
```

Expected output (values are the stub's invented example values):

```text
span name : provecart.verify
kind      : SpanKind.CLIENT
status    : OK
attributes:
  provecart.correction_count = 1
  provecart.mandate_kind = 'cart'
  provecart.record_id = 'rec_example_0001'
  provecart.spec_version = 'acf-0.1'
  provecart.verdict = 'REVIEW'
OK: span emitted, attribute set matches the spec exactly.
```

The script fails loudly if the emitted attribute set ever drifts
from the spec's closed list — that assertion is the redaction rule,
made executable.
