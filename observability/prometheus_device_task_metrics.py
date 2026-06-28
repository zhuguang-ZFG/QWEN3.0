"""Prometheus instrumentation for device task lifecycle."""

from __future__ import annotations

from observability import prometheus_metrics as _pm


def record_device_task_issued(capability: str, source: str) -> None:
    """Record that a device task was issued."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("device_tasks_issued")
    if counter:
        counter.labels(capability=capability or "unknown", source=source or "unknown").inc()


def record_device_task_dispatched(capability: str, status: str) -> None:
    """Record a dispatch attempt result (sent, queued, failed)."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("device_tasks_dispatched")
    if counter:
        counter.labels(capability=capability or "unknown", status=status or "unknown").inc()


def record_device_task_dispatch_failure(reason: str) -> None:
    """Record a dispatch failure reason (e.g. attestation, websocket_error)."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("device_task_dispatch_failures")
    if counter:
        counter.labels(reason=reason or "unknown").inc()


def record_device_task_retry(capability: str) -> None:
    """Record a task retry."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("device_task_retries")
    if counter:
        counter.labels(capability=capability or "unknown").inc()


def record_device_task_dead_letter(capability: str) -> None:
    """Record a task abandoned after exceeding max retries."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("device_tasks_dead_letter")
    if counter:
        counter.labels(capability=capability or "unknown").inc()


def set_device_tasks_pending(count: int) -> None:
    """Update the gauge of total pending device tasks."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    gauge = _pm._gauges.get("device_tasks_pending")
    if gauge:
        gauge.set(max(0, int(count)))
