"""Tests for observability/metrics.py — in-memory metrics aggregation."""

from observability.metrics import record, get_metrics_snapshot, reset_metrics
from observability.events import LiMaEvent


def setup_function():
    reset_metrics()


class TestRecord:
    def test_record_request_start(self):
        record(LiMaEvent(event_type="request_start", backend="groq"))
        s = get_metrics_snapshot()
        assert s["total_requests"] >= 1

    def test_record_success(self):
        record(LiMaEvent(event_type="request_complete", backend="groq", latency_ms=150))
        s = get_metrics_snapshot()
        assert s["total_requests"] >= 1

    def test_record_failure(self):
        record(LiMaEvent(event_type="request_complete", backend="groq", failure_class="timeout"))
        s = get_metrics_snapshot()

    def test_record_token_usage(self):
        record(LiMaEvent(event_type="token_usage", backend="groq", prompt_tokens=100, completion_tokens=50))
        s = get_metrics_snapshot()

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

    def test_multiple_events(self):
        for i in range(5):
            record(LiMaEvent(event_type="request_start", backend=f"b{i}"))
        s = get_metrics_snapshot()
        assert s["total_requests"] == 5
