"""Tests for observability/metrics.py — in-memory metrics aggregation."""

from observability.metrics import (
    record,
    get_metrics_snapshot,
    reset_metrics,
    get_top_failing_backends,
    get_top_quality_backends,
    get_fastest_growing_failure_class,
)
from observability.events import (
    LiMaEvent,
    request_start_event,
    backend_call_event,
    backend_error_event,
    quality_result_event,
    token_usage_event,
)


def setup_function():
    reset_metrics()


class TestRecord:
    def test_record_request_start(self):
        record(LiMaEvent(event_type="request_start", backend="groq"))
        s = get_metrics_snapshot()
        assert s["total_requests"] == 1
        assert s["event_type_counts"]["request_start"] == 1

    def test_record_success_tracks_backend(self):
        record(LiMaEvent(event_type="backend_call", backend="groq", latency_ms=150))
        s = get_metrics_snapshot()
        assert s["backends"]["groq"]["success"] == 1
        assert s["backends"]["groq"]["avg_latency_ms"] == 150

    def test_record_failure_tracks_failure_class(self):
        record(LiMaEvent(event_type="backend_error", backend="groq", failure_class="timeout"))
        s = get_metrics_snapshot()
        assert s["backends"]["groq"]["failure"] == 1
        assert s["failure_class_counts"]["timeout"] == 1

    def test_record_token_usage_tracks_tokens(self):
        record(LiMaEvent(event_type="token_usage", backend="groq", prompt_tokens=100, completion_tokens=50))
        s = get_metrics_snapshot()
        assert s["backends"]["groq"]["prompt_tokens"] == 100
        assert s["backends"]["groq"]["completion_tokens"] == 50
        assert s["backends"]["groq"]["token_requests"] == 1

    def test_summary_has_expected_keys(self):
        record(LiMaEvent(event_type="request_start", backend="test"))
        s = get_metrics_snapshot()
        assert "total_requests" in s
        assert "uptime_seconds" in s
        assert "backends" in s

    def test_reset_clears_counters(self):
        record(LiMaEvent(event_type="request_start", backend="test"))
        s1 = get_metrics_snapshot()
        assert s1["total_requests"] > 0
        reset_metrics()
        s2 = get_metrics_snapshot()
        assert s2["total_requests"] == 0
        assert s2["event_type_counts"] == {}
        assert s2["backends"] == {}

    def test_multiple_events(self):
        for i in range(5):
            record(LiMaEvent(event_type="request_start", backend=f"b{i}"))
        s = get_metrics_snapshot()
        assert s["total_requests"] == 5


# -- detailed aggregation coverage from former tests/test_observability.py ------


def test_record_request_start_increments_total():
    record(request_start_event("r1"))
    snapshot = get_metrics_snapshot()
    assert snapshot["total_requests"] == 1


def test_record_backend_call_tracks_success():
    record(backend_call_event("r1", "scnet_ds_flash", "coding"))
    snapshot = get_metrics_snapshot()
    assert snapshot["backends"]["scnet_ds_flash"]["success"] == 1


def test_record_backend_error_tracks_failure_class():
    record(backend_error_event("r1", "groq", "rate_limited"))
    snapshot = get_metrics_snapshot()
    assert snapshot["backends"]["groq"]["failure"] == 1
    assert snapshot["failure_class_counts"]["rate_limited"] == 1


def test_record_latency_tracks_percentiles():
    for i in range(10):
        e = backend_call_event(f"r{i}", "test_backend", "test")
        e.latency_ms = float(i * 10 + 10)  # 10, 20, ..., 100
        record(e)
    snapshot = get_metrics_snapshot()
    stats = snapshot["backends"]["test_backend"]
    assert abs(stats["avg_latency_ms"] - 55.0) < 1.0
    assert stats["p50_latency_ms"] >= 50
    assert stats["p95_latency_ms"] >= 80


def test_record_quality_tracks_avg():
    for score in [0.5, 0.7, 0.9, 0.3]:
        record(quality_result_event("r", "test_backend", score, score >= 0.5))
    snapshot = get_metrics_snapshot()
    avg = snapshot["backends"]["test_backend"]["avg_quality_score"]
    assert 0.5 <= avg <= 0.7


def test_record_token_usage_accumulates():
    record(token_usage_event("scnet", 100, 50, "free"))
    record(token_usage_event("scnet", 200, 100, "free"))
    snapshot = get_metrics_snapshot()
    stats = snapshot["backends"]["scnet"]
    assert stats["prompt_tokens"] == 300
    assert stats["completion_tokens"] == 150
    assert stats["token_requests"] == 2


def test_snapshot_isolation():
    """Metric snapshots reflect state at capture time."""
    record(backend_call_event("r1", "a", "test"))
    snap1 = get_metrics_snapshot()
    assert snap1["backends"]["a"]["success"] == 1
    record(backend_call_event("r2", "b", "test"))
    snap2 = get_metrics_snapshot()
    assert "b" in snap2["backends"]
    assert snap1.get("backends", {}).get("b") is None


def test_get_top_failing_backends():
    for b in ["a", "b", "c"]:
        for _ in range({"a": 5, "b": 3, "c": 1}[b]):
            record(backend_error_event("r", b, "timeout"))
    top = get_top_failing_backends(2)
    assert top[0][0] == "a"
    assert top[0][1] == 5
    assert len(top) == 2


def test_get_top_quality_backends():
    for b, scores in [("good", [0.9, 0.95, 0.92]), ("bad", [0.3, 0.4, 0.35]), ("ok", [0.6, 0.7])]:
        for s in scores:
            record(quality_result_event("r", b, s, s >= 0.5))
    top = get_top_quality_backends(3)
    assert top[0][0] == "good"
    assert top[0][1] >= 0.9


def test_get_fastest_growing_failure_class():
    for cls, count in [("rate_limited", 10), ("auth_expired", 3), ("timeout", 1)]:
        for _ in range(count):
            record(backend_error_event("r", "x", cls))
    top = get_fastest_growing_failure_class(3)
    assert top[0][0] == "rate_limited"
    assert top[0][1] == 10


def test_snapshot_never_contains_raw_key():
    snapshot = get_metrics_snapshot()
    text = str(snapshot)
    assert "sk-" not in text


def test_snapshot_never_contains_raw_prompt():
    record(backend_call_event("r1", "test", "coding", session_id="user_session_123"))
    snapshot = get_metrics_snapshot()
    text = str(snapshot)
    assert "user_session_123" not in text


def test_event_type_counts_accurate():
    for _ in range(3):
        record(request_start_event("r"))
    for _ in range(5):
        record(backend_call_event("r", "b", "t"))
    for _ in range(2):
        record(backend_error_event("r", "b", "timeout"))

    snapshot = get_metrics_snapshot()
    assert snapshot["event_type_counts"]["request_start"] == 3
    assert snapshot["event_type_counts"]["backend_call"] == 5
    assert snapshot["event_type_counts"]["backend_error"] == 2


def test_openobserve_enabled_without_sink_is_visible(monkeypatch, caplog):
    monkeypatch.setenv("OPENOBSERVE_ENABLED", "1")

    record(request_start_event("r-openobserve"))

    snapshot = get_metrics_snapshot()
    assert snapshot["openobserve"]["enabled"] is True
    assert snapshot["openobserve"]["available"] is False
    assert "openobserve export enabled but sink unavailable" in caplog.text
