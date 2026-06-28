"""Prometheus instrumentation for image generation."""

from __future__ import annotations

from observability import prometheus_metrics as _pm


def record_image_cache_lookup(result: str) -> None:
    """Record an image cache lookup as hit or miss."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("image_cache_lookups")
    if counter:
        normalized = "hit" if result == "hit" else "miss"
        counter.labels(result=normalized).inc()


def record_image_request(backend: str) -> None:
    """Record an image generation request by the backend that served it."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    counter = _pm._counters.get("image_requests")
    if counter:
        counter.labels(backend=backend or "unknown").inc()


def record_image_cache_entries(count: int) -> None:
    """Update the gauge of current image cache entries."""
    if not _pm.is_enabled():
        return
    _pm._ensure_instruments()
    gauge = _pm._gauges.get("image_cache_entries")
    if gauge:
        gauge.set(float(count))
