"""Tests for gray-observation metrics aggregation."""

from observability.events import (
    instructor_intent_event,
    instructor_intent_latency_event,
    semantic_cache_event,
)
from observability.metrics import get_metrics_snapshot, record, reset_metrics


def setup_function():
    reset_metrics()


def test_semantic_cache_hit_rate_and_latency():
    for _ in range(5):
        record(semantic_cache_event("hit", latency_ms=10.0))
    for _ in range(3):
        record(semantic_cache_event("miss", latency_ms=20.0))
    record(semantic_cache_event("error", latency_ms=5.0))
    record(semantic_cache_event("store"))
    record(semantic_cache_event("skip"))

    gray = get_metrics_snapshot()["gray_observation"]
    sc = gray["semantic_cache"]
    assert sc["hit"] == 5
    assert sc["miss"] == 3
    assert sc["error"] == 1
    assert sc["store"] == 1
    assert sc["skip"] == 1
    assert abs(sc["hit_rate"] - 5 / 9) < 0.001
    assert abs(sc["avg_lookup_ms"] - (5 * 10 + 3 * 20 + 5) / 9) < 0.5
    assert sc["p95_lookup_ms"] == 20.0


def test_instructor_intent_success_rate_and_latency():
    record(instructor_intent_event("openai", "gpt-4o-mini", True))
    record(instructor_intent_event("openai", "gpt-4o-mini", False))
    record(instructor_intent_event("openai", "gpt-4o-mini", False))
    record(instructor_intent_event("openai", "gpt-4o-mini", False, reason="timeout"))

    for latency in [10.0, 20.0, 30.0, 40.0, 50.0]:
        record(instructor_intent_latency_event("openai", "gpt-4o-mini", latency))

    gray = get_metrics_snapshot()["gray_observation"]
    intent = gray["instructor_intent"]
    assert intent["success"] == 1
    assert intent["failure"] == 3
    assert abs(intent["success_rate"] - 0.25) < 0.001
    assert intent["avg_latency_ms"] == 30.0
    assert intent["p95_latency_ms"] == 50.0


def test_reset_clears_gray_observation():
    record(semantic_cache_event("hit", latency_ms=10.0))
    record(instructor_intent_event("p", "m", True))
    record(instructor_intent_latency_event("p", "m", 12.0))

    reset_metrics()
    gray = get_metrics_snapshot()["gray_observation"]
    assert gray["semantic_cache"]["hit"] == 0
    assert gray["semantic_cache"]["avg_lookup_ms"] == 0
    assert gray["instructor_intent"]["success"] == 0
    assert gray["instructor_intent"]["avg_latency_ms"] == 0


def test_event_type_counts_include_gray_events():
    record(semantic_cache_event("hit"))
    record(semantic_cache_event("miss"))
    record(instructor_intent_event("p", "m", True))

    snapshot = get_metrics_snapshot()
    assert snapshot["event_type_counts"]["semantic_cache_hit"] == 1
    assert snapshot["event_type_counts"]["semantic_cache_miss"] == 1
    assert snapshot["event_type_counts"]["instructor_intent_success"] == 1
