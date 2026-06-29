"""Tests for AUDIT-5-O10 backend telemetry aggregation."""

from __future__ import annotations

from observability.telemetry_aggregator import BackendTelemetryAggregator


def test_aggregator_combines_duplicate_records():
    flushed: list[dict] = []
    aggregator = BackendTelemetryAggregator(lambda records: flushed.extend(records))

    base = {
        "ts": 1,
        "backend": "groq",
        "scenario": "chat",
        "request_type": "text",
        "phase": "route",
        "attempt": "serial",
        "model": "llama",
        "success": False,
        "latency_ms": 100,
        "tools_requested": False,
        "status_code": 429,
        "error_class": "rate_limit",
    }
    for _ in range(5):
        aggregator.record(base)

    aggregator.flush()
    assert len(flushed) == 1
    assert flushed[0]["count"] == 5
    assert flushed[0]["latency_ms"] == 100


def test_aggregator_keeps_distinct_records_separate():
    flushed: list[dict] = []
    aggregator = BackendTelemetryAggregator(lambda records: flushed.extend(records))

    a = {
        "ts": 1,
        "backend": "groq",
        "scenario": "chat",
        "request_type": "text",
        "phase": "route",
        "attempt": "serial",
        "model": "llama",
        "success": False,
        "latency_ms": 100,
        "tools_requested": False,
        "status_code": 429,
        "error_class": "rate_limit",
    }
    b = dict(a)
    b["backend"] = "openrouter"
    aggregator.record(a)
    aggregator.record(b)
    aggregator.flush()

    assert len(flushed) == 2
    backends = {r["backend"] for r in flushed}
    assert backends == {"groq", "openrouter"}


def test_aggregator_updates_latency_and_count():
    flushed: list[dict] = []
    aggregator = BackendTelemetryAggregator(lambda records: flushed.extend(records))

    base = {
        "ts": 1,
        "backend": "groq",
        "scenario": "chat",
        "request_type": "text",
        "phase": "route",
        "attempt": "serial",
        "model": "llama",
        "success": False,
        "latency_ms": 100,
        "tools_requested": False,
        "status_code": 429,
        "error_class": "rate_limit",
    }
    aggregator.record(base)
    bigger = dict(base)
    bigger["latency_ms"] = 250
    aggregator.record(bigger)
    aggregator.flush()

    assert flushed[0]["count"] == 2
    assert flushed[0]["latency_ms"] == 250


def test_aggregator_flushes_when_unique_threshold_reached():
    from observability.telemetry_aggregator import MAX_BUFFER_UNIQUE

    flushed: list[dict] = []
    aggregator = BackendTelemetryAggregator(lambda records: flushed.extend(records))
    base = {
        "ts": 1,
        "backend": "groq",
        "scenario": "chat",
        "request_type": "text",
        "phase": "route",
        "attempt": "serial",
        "model": "llama",
        "success": False,
        "latency_ms": 100,
        "tools_requested": False,
        "status_code": 429,
        "error_class": "rate_limit",
    }
    for i in range(MAX_BUFFER_UNIQUE):
        rec = dict(base)
        rec["backend"] = f"backend-{i}"
        aggregator.record(rec)

    assert len(flushed) == MAX_BUFFER_UNIQUE
