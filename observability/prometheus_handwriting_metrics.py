"""Prometheus instrumentation for handwriting requests."""

from __future__ import annotations

from observability import prometheus_metrics as _pm


def record_handwriting_request(status: str, *, fallback: bool = False) -> None:
    """Record a handwriting request by final status and whether local fallback was used."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("handwriting_requests")
    if counter:
        counter.labels(status=status or "unknown", fallback="true" if fallback else "false").inc()


def record_handwriting_duration(duration_ms: float, *, status: str = "unknown") -> None:
    """Record the duration of a handwriting request."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    histogram = _pm._histograms.get("handwriting_duration")
    if histogram:
        histogram.labels(status=status).observe(max(0.0, float(duration_ms)))
