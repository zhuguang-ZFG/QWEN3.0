"""Streaming failover metrics tracking.

Records mid-stream failover events for operational visibility.
Provides an in-memory ring buffer of recent failover events and
aggregate statistics for the /v1/ops/metrics endpoint.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FailoverEvent:
    """A single mid-stream failover event."""

    timestamp: float = field(default_factory=time.time)
    failed_backend: str = ""
    replacement_backend: str = ""
    chunks_before_failure: int = 0
    text_length_before_failure: int = 0
    elapsed_sec: float = 0.0
    failure_reason: str = ""
    success: bool | None = None  # None = unknown, True = recovery succeeded
    backends_tried: list[str] = field(default_factory=list)


class FailoverMetrics:
    """Thread-safe in-memory metrics store for streaming failovers.

    Maintains a ring buffer of recent events and running aggregates.
    """

    def __init__(self, max_events: int = 500) -> None:
        self._lock = threading.Lock()
        self._events: deque[FailoverEvent] = deque(maxlen=max_events)
        self._total_failovers: int = 0
        self._total_successes: int = 0
        self._total_failures: int = 0
        self._total_chunks_before_failure: int = 0

    def record(self, event: FailoverEvent) -> None:
        """Record a failover event.

        Args:
            event: The failover event to record.
        """
        with self._lock:
            self._events.append(event)
            self._total_failovers += 1
            if event.success is True:
                self._total_successes += 1
            elif event.success is False:
                self._total_failures += 1
            self._total_chunks_before_failure += event.chunks_before_failure

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate failover statistics.

        Returns:
            Dict with aggregate stats:
              - total_failovers: Total number of failover events.
              - success_count: Failovers where recovery succeeded.
              - failure_count: Failovers where recovery also failed.
              - unknown_count: Failovers with unknown outcome.
              - success_rate: Fraction of failovers that succeeded (0.0-1.0).
              - avg_chunks_before_failure: Average chunks received before failure.
              - recent_events: Last 10 failover events (as dicts).
        """
        with self._lock:
            total = self._total_failovers
            successes = self._total_successes
            failures = self._total_failures
            unknown = total - successes - failures

            success_rate = (
                successes / total if total > 0 else 0.0
            )
            avg_chunks = (
                self._total_chunks_before_failure / total
                if total > 0
                else 0.0
            )

            recent = [asdict(e) for e in list(self._events)[-10:]]

        return {
            "total_failovers": total,
            "success_count": successes,
            "failure_count": failures,
            "unknown_count": unknown,
            "success_rate": round(success_rate, 4),
            "avg_chunks_before_failure": round(avg_chunks, 2),
            "recent_events": recent,
        }

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        """Return the most recent failover events.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of event dicts, most recent last.
        """
        with self._lock:
            return [asdict(e) for e in list(self._events)[-limit:]]

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._events.clear()
            self._total_failovers = 0
            self._total_successes = 0
            self._total_failures = 0
            self._total_chunks_before_failure = 0


# Module-level singleton
_metrics = FailoverMetrics()


def get_failover_metrics() -> FailoverMetrics:
    """Return the global FailoverMetrics singleton."""
    return _metrics


def record_stream_failover(
    failed_backend: str,
    replacement_backend: str,
    state_snapshot: dict,
    *,
    success: bool | None = None,
) -> None:
    """Convenience function to record a failover event.

    Called from the on_failover callback in bridge_stream_async.

    Args:
        failed_backend: The backend that failed.
        replacement_backend: The backend being switched to.
        state_snapshot: Snapshot dict from StreamState.snapshot().
        success: Whether the failover recovery succeeded.
    """
    event = FailoverEvent(
        failed_backend=failed_backend,
        replacement_backend=replacement_backend,
        chunks_before_failure=state_snapshot.get("chunk_count", 0),
        text_length_before_failure=state_snapshot.get("text_length", 0),
        elapsed_sec=state_snapshot.get("elapsed_sec", 0.0),
        failure_reason=state_snapshot.get("failure_reason", ""),
        success=success,
        backends_tried=state_snapshot.get("backends_tried", []),
    )
    _metrics.record(event)
