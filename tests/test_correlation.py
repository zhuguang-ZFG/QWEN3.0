"""Tests for observability/correlation.py — cross-system event tracing."""

from observability.correlation import (
    record_request_correlation,
    record_worker_task_correlation,
    record_device_task_correlation,
    record_motion_event_correlation,
    correlate_by_id,
    correlate_recent,
    correlation_summary,
    _events,
)


def setup_function():
    _events.clear()


class TestRecordAndCorrelate:
    def test_record_request(self):
        record_request_correlation("req-1", "groq", "success", latency_ms=150)
        results = correlate_by_id("req-1")
        assert len(results) >= 1
        assert results[0]["type"] == "request"
        assert results[0]["backend"] == "groq"

    def test_record_worker_task(self):
        record_worker_task_correlation("task-1", "completed", worker_id="w-1")
        results = correlate_by_id("task-1")
        assert len(results) >= 1
        assert results[0]["type"] == "worker_task"

    def test_record_device_task(self):
        record_device_task_correlation("task-d1", "dev-1", "running")
        results = correlate_by_id("task-d1")
        assert len(results) >= 1
        assert results[0]["type"] == "device_task"

    def test_record_motion_event(self):
        record_motion_event_correlation("task-1", "dev-1", "done")
        results = correlate_by_id("task-1")
        # Should find both device_task and motion_event
        assert len(results) >= 1
        assert any(e["type"] == "motion_event" for e in results)

    def test_correlate_by_device_id(self):
        record_device_task_correlation("t1", "dev-42", "failed", error_code="ERR")
        record_device_task_correlation("t2", "dev-42", "done")
        results = correlate_by_id("dev-42")
        assert len(results) == 2

    def test_correlate_empty_id(self):
        assert correlate_by_id("") == []
        assert correlate_by_id("  ") == []


class TestCorrelateRecent:
    def test_returns_recent_events(self):
        record_request_correlation("r1", "b1", "ok")
        record_request_correlation("r2", "b2", "ok")
        recent = correlate_recent(limit=10)
        assert len(recent) >= 2

    def test_limit_respected(self):
        for i in range(20):
            record_request_correlation(f"r{i}", "b", "ok")
        recent = correlate_recent(limit=5)
        assert len(recent) <= 5


class TestCorrelationSummary:
    def test_summary_counts(self):
        record_request_correlation("r1", "b", "success")
        record_request_correlation("r2", "b", "failed", error_code="500")
        record_device_task_correlation("t1", "d1", "done")
        summary = correlation_summary()
        assert summary["total_events"] >= 3
        assert summary["by_type"].get("request", 0) >= 2
        assert summary["by_status"].get("success") >= 1

    def test_error_ids_tracked(self):
        record_device_task_correlation("err-task", "d1", "failed", error_code="ERR")
        summary = correlation_summary()
        assert "err-task" in summary["recent_error_task_ids"]


class TestCorrelatedEvent:
    def test_to_dict_omits_empty_fields(self):
        from observability.correlation import CorrelatedEvent

        event = CorrelatedEvent(timestamp=100.0, event_type="request")
        d = event.to_dict()
        assert d["ts"] == 100.0
        assert d["type"] == "request"
        assert "backend" not in d  # empty field omitted

    def test_to_dict_includes_extra(self):
        from observability.correlation import CorrelatedEvent

        event = CorrelatedEvent(timestamp=100.0, event_type="request", extra={"source": "test"})
        d = event.to_dict()
        assert d["extra"]["source"] == "test"
