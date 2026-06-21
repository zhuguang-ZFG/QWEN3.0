"""Cross-system correlation index — links request, worker, and device spans.

Lightweight ring buffer that records touchpoints across subsystems so
an operator can trace a request_id, task_id, or device_id through every
system it reached, with failure reasons at each hop.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

MAX_EVENTS = 500


@dataclass
class CorrelatedEvent:
    timestamp: float
    event_type: str  # "request" | "worker_task" | "device_task" | "motion_event"
    request_id: str = ""
    task_id: str = ""
    device_id: str = ""
    backend: str = ""
    status: str = ""
    error_code: str = ""
    error_reason: str = ""
    latency_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "ts": self.timestamp,
            "type": self.event_type,
        }
        for key in (
            "request_id",
            "task_id",
            "device_id",
            "backend",
            "status",
            "error_code",
            "error_reason",
            "latency_ms",
        ):
            val = getattr(self, key)
            if val:
                d[key] = val
        if self.extra:
            d["extra"] = self.extra
        return d


_events: deque[CorrelatedEvent] = deque(maxlen=MAX_EVENTS)
_lock = threading.Lock()


def record_request_correlation(
    request_id: str,
    backend: str,
    status: str,
    latency_ms: int = 0,
    error_code: str = "",
    error_reason: str = "",
) -> None:
    with _lock:
        _events.append(
            CorrelatedEvent(
                timestamp=time.time(),
                event_type="request",
                request_id=request_id,
                backend=backend,
                status=status,
                latency_ms=latency_ms,
                error_code=error_code,
                error_reason=error_reason,
            )
        )


def record_worker_task_correlation(
    task_id: str,
    status: str,
    worker_id: str = "",
) -> None:
    with _lock:
        _events.append(
            CorrelatedEvent(
                timestamp=time.time(),
                event_type="worker_task",
                task_id=task_id,
                status=status,
                extra={"worker_id": worker_id} if worker_id else {},
            )
        )


def record_device_task_correlation(
    task_id: str,
    device_id: str,
    status: str,
    error_code: str = "",
    error_reason: str = "",
) -> None:
    with _lock:
        _events.append(
            CorrelatedEvent(
                timestamp=time.time(),
                event_type="device_task",
                task_id=task_id,
                device_id=device_id,
                status=status,
                error_code=error_code,
                error_reason=error_reason,
            )
        )


def record_motion_event_correlation(
    task_id: str,
    device_id: str,
    phase: str,
    error_code: str = "",
    error_reason: str = "",
) -> None:
    with _lock:
        _events.append(
            CorrelatedEvent(
                timestamp=time.time(),
                event_type="motion_event",
                task_id=task_id,
                device_id=device_id,
                status=phase,
                error_code=error_code,
                error_reason=error_reason,
            )
        )


def correlate_by_id(target_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Find all events matching a request_id, task_id, or device_id."""
    if not target_id or not str(target_id).strip():
        return []
    target = str(target_id).strip()
    with _lock:
        matched = [
            e
            for e in _events
            if target == (e.request_id or "") or target == (e.task_id or "") or target == (e.device_id or "")
        ]
    return [e.to_dict() for e in matched[-limit:]]


def correlate_recent(limit: int = 30) -> list[dict[str, Any]]:
    """Return most recent correlation events."""
    with _lock:
        recent = list(_events)[-limit:]
    return [e.to_dict() for e in recent]


def correlation_summary() -> dict[str, Any]:
    """Return a summary of recent correlation data."""
    with _lock:
        recent = list(_events)[-200:]
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    error_ids: list[str] = []
    for e in recent:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        if e.status:
            by_status[e.status] = by_status.get(e.status, 0) + 1
        if e.error_code and e.task_id and e.task_id not in error_ids:
            error_ids.append(e.task_id)
    return {
        "total_events": len(recent),
        "by_type": by_type,
        "by_status": by_status,
        "recent_error_task_ids": error_ids[-10:],
    }
