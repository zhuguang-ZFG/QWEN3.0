"""Tests for streaming failover metrics."""

import time
from unittest.mock import patch

import pytest

from streaming_failover_metrics import (
    FailoverEvent,
    FailoverMetrics,
    get_failover_metrics,
    record_stream_failover,
)


class TestFailoverEvent:
    def test_defaults(self):
        event = FailoverEvent()
        assert event.failed_backend == ""
        assert event.replacement_backend == ""
        assert event.chunks_before_failure == 0
        assert event.success is None
        assert event.timestamp > 0

    def test_custom_values(self):
        event = FailoverEvent(
            failed_backend="backend_a",
            replacement_backend="backend_b",
            chunks_before_failure=42,
            text_length_before_failure=500,
            success=True,
        )
        assert event.failed_backend == "backend_a"
        assert event.success is True


class TestFailoverMetrics:
    def test_empty_stats(self):
        m = FailoverMetrics()
        stats = m.get_stats()
        assert stats["total_failovers"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_chunks_before_failure"] == 0.0
        assert stats["recent_events"] == []

    def test_record_single_event(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(
            failed_backend="a",
            replacement_backend="b",
            chunks_before_failure=10,
            success=True,
        ))
        stats = m.get_stats()
        assert stats["total_failovers"] == 1
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["avg_chunks_before_failure"] == 10.0

    def test_record_multiple_events(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(success=True, chunks_before_failure=10))
        m.record(FailoverEvent(success=False, chunks_before_failure=20))
        m.record(FailoverEvent(success=None, chunks_before_failure=30))

        stats = m.get_stats()
        assert stats["total_failovers"] == 3
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["unknown_count"] == 1
        assert stats["success_rate"] == pytest.approx(1 / 3, abs=0.01)
        assert stats["avg_chunks_before_failure"] == 20.0

    def test_ring_buffer(self):
        m = FailoverMetrics(max_events=3)
        for i in range(5):
            m.record(FailoverEvent(failed_backend=f"b{i}"))

        recent = m.get_recent_events(limit=10)
        assert len(recent) == 3
        assert recent[0]["failed_backend"] == "b2"
        assert recent[2]["failed_backend"] == "b4"

    def test_get_recent_events_limit(self):
        m = FailoverMetrics()
        for i in range(10):
            m.record(FailoverEvent(failed_backend=f"b{i}"))

        assert len(m.get_recent_events(limit=3)) == 3
        assert len(m.get_recent_events(limit=100)) == 10

    def test_reset(self):
        m = FailoverMetrics()
        m.record(FailoverEvent(success=True))
        m.reset()
        stats = m.get_stats()
        assert stats["total_failovers"] == 0


class TestRecordStreamFailover:
    def test_convenience_function(self):
        # Use a fresh metrics instance to avoid pollution from other tests
        fresh = FailoverMetrics()
        with patch("streaming_failover_metrics._metrics", fresh):
            record_stream_failover(
                "backend_a",
                "backend_b",
                {
                    "chunk_count": 15,
                    "text_length": 200,
                    "elapsed_sec": 3.5,
                    "failure_reason": "timeout",
                    "backends_tried": ["backend_a", "backend_b"],
                },
                success=True,
            )

            stats = fresh.get_stats()
            assert stats["total_failovers"] == 1
            assert stats["success_count"] == 1
            event = stats["recent_events"][0]
            assert event["failed_backend"] == "backend_a"
            assert event["replacement_backend"] == "backend_b"
            assert event["chunks_before_failure"] == 15

    def test_global_singleton(self):
        metrics = get_failover_metrics()
        assert isinstance(metrics, FailoverMetrics)
