"""Reference example: one provecart.verify span around a stubbed check.

Implements docs/otel/verdict-span-spec.md. The check call is stubbed
(mock mode): no network, no credentials, no real transaction. The
stub returns the *shape* of a check response — a record id, a
verdict, a mandate kind, a correction count, a spec version — which
is all the span is ever allowed to see.

Run (offline):

    pip install opentelemetry-api opentelemetry-sdk
    python verify_span.py

The span is exported to an in-memory exporter and printed at the
end. Inspect the printed attribute set: it is exactly the closed
list from the spec, and nothing in it can reconstruct the order.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


def stubbed_check():
    """Mock mode stand-in for a ProveCart check call.

    A real integration replaces this one function with its HTTP call
    and maps the response fields. Nothing else in this file changes.
    The values below are invented for the example.
    """
    return {
        "record_id": "rec_example_0001",
        "verdict": "REVIEW",
        "mandate_kind": "cart",
        "corrections": [{"code": "EXAMPLE_ONLY"}],
        "spec_version": "acf-0.1",
    }


def main():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("provecart.example")

    result = stubbed_check()

    # The span carries identifiers and outcome only — see the
    # redaction rule in the spec. No instruction text, no item
    # names, no prices: they are not read here at all.
    with tracer.start_as_current_span(
        "provecart.verify", kind=trace.SpanKind.CLIENT
    ) as span:
        span.set_attribute("provecart.record_id", result["record_id"])
        span.set_attribute("provecart.verdict", result["verdict"])
        span.set_attribute("provecart.mandate_kind", result["mandate_kind"])
        span.set_attribute(
            "provecart.correction_count", len(result["corrections"])
        )
        span.set_attribute("provecart.spec_version", result["spec_version"])
        span.set_status(trace.Status(trace.StatusCode.OK))

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1, f"expected exactly 1 span, got {len(spans)}"
    span = spans[0]
    print(f"span name : {span.name}")
    print(f"kind      : {span.kind}")
    print(f"status    : {span.status.status_code.name}")
    print("attributes:")
    for key in sorted(span.attributes):
        print(f"  {key} = {span.attributes[key]!r}")
    allowed = {
        "provecart.record_id",
        "provecart.verdict",
        "provecart.mandate_kind",
        "provecart.correction_count",
        "provecart.spec_version",
    }
    assert set(span.attributes) == allowed, (
        f"attribute set drifted from the spec: {sorted(span.attributes)}"
    )
    print("OK: span emitted, attribute set matches the spec exactly.")


if __name__ == "__main__":
    main()
