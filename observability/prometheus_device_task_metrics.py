"""Prometheus instrumentation for device task lifecycle."""

from __future__ import annotations

from observability import prometheus_metrics as _pm


def _ensure_device_task_counters() -> None:
    """Lazy-register device-task counters after the main registry is ready."""
    if "device_tasks_issued" in _pm._counters:
        return
    registry = _pm._registry
    if registry is None:
        return
    client = _pm._load_client()
    counter = client["Counter"]
    _pm._counters["device_tasks_issued"] = counter(
        "lima_device_tasks_issued_total",
        "Device tasks issued",
        ["capability", "source"],
        registry=registry,
    )
    _pm._counters["device_tasks_dispatched"] = counter(
        "lima_device_tasks_dispatched_total",
        "Device tasks dispatched",
        ["capability", "status"],
        registry=registry,
    )
    _pm._counters["device_task_dispatch_failures"] = counter(
        "lima_device_task_dispatch_failures_total",
        "Device task dispatch failures",
        ["reason"],
        registry=registry,
    )
    _pm._counters["device_task_retries"] = counter(
        "lima_device_task_retries_total",
        "Device task retries",
        ["capability"],
        registry=registry,
    )
    _pm._counters["device_tasks_dead_letter"] = counter(
        "lima_device_tasks_dead_letter_total",
        "Device tasks abandoned after max retries",
        ["capability"],
        registry=registry,
    )


def record_device_task_issued(capability: str, source: str) -> None:
    """Record that a device task was issued."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    _ensure_device_task_counters()
    counter = _pm._counters.get("device_tasks_issued")
    if counter:
        counter.labels(capability=capability or "unknown", source=source or "unknown").inc()


def record_device_task_dispatched(capability: str, status: str) -> None:
    """Record a dispatch attempt result (sent, queued, failed)."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    _ensure_device_task_counters()
    counter = _pm._counters.get("device_tasks_dispatched")
    if counter:
        counter.labels(capability=capability or "unknown", status=status or "unknown").inc()


def record_device_task_dispatch_failure(reason: str) -> None:
    """Record a dispatch failure reason (e.g. attestation, websocket_error)."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    _ensure_device_task_counters()
    counter = _pm._counters.get("device_task_dispatch_failures")
    if counter:
        counter.labels(reason=reason or "unknown").inc()


def record_device_task_retry(capability: str) -> None:
    """Record a task retry."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    _ensure_device_task_counters()
    counter = _pm._counters.get("device_task_retries")
    if counter:
        counter.labels(capability=capability or "unknown").inc()


def record_device_task_dead_letter(capability: str) -> None:
    """Record a task abandoned after exceeding max retries."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    _ensure_device_task_counters()
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
