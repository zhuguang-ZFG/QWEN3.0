"""Prometheus metrics for startup phases and backend retirement.

These instruments are registered in :mod:`observability.prometheus_metrics`;
this module only holds the recording helpers to keep the main metrics file small.
"""

from __future__ import annotations

import logging

from observability import prometheus_metrics as _prom

_log = logging.getLogger(__name__)


def record_backend_retirement_event(backend: str) -> None:
    """Increment retirement counter when a backend is newly retired."""
    if not _prom.is_enabled():
        return
    _prom._ensure_instruments()
    counter = _prom._counters.get("backend_retirement_events")
    if counter:
        counter.labels(backend=backend).inc()


def record_startup_phase(phase: str, elapsed_ms: float) -> None:
    """Record the duration of a single lifespan startup phase."""
    if not _prom.is_enabled():
        return
    try:
        _prom._ensure_instruments()
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to ensure Prometheus instruments for startup phase: %s", exc)
        return
    h = _prom._histograms.get("startup_phase_duration")
    if h:
        h.labels(phase=phase).observe(float(elapsed_ms))


def record_startup_status(status: str) -> None:
    """Record the current startup status as a gauge value."""
    if not _prom.is_enabled():
        return
    try:
        _prom._ensure_instruments()
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to ensure Prometheus instruments for startup status: %s", exc)
        return
    g = _prom._gauges.get("startup_status")
    if g:
        g.set(_prom._STARTUP_STATUS_VALUES.get(status, 0.0))


def sync_retired_backends(retired: set[str]) -> None:
    """Sync per-backend retired gauges and aggregate count from backend_retirement."""
    if not _prom.is_enabled():
        return
    _prom._ensure_instruments()
    retired_gauge = _prom._gauges.get("backend_retired")
    count_gauge = _prom._gauges.get("backend_retired_count")
    if not retired_gauge or not count_gauge:
        return

    normalized = {name for name in retired if name}
    for backend in normalized - _prom._retired_backend_labels:
        retired_gauge.labels(backend=backend).set(1.0)
    for backend in _prom._retired_backend_labels - normalized:
        retired_gauge.labels(backend=backend).set(0.0)
    _prom._retired_backend_labels.clear()
    _prom._retired_backend_labels.update(normalized)
    count_gauge.set(float(len(normalized)))
