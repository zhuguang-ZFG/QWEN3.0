"""Prometheus metrics endpoint for LiMa.

Enabled via LIMA_PROMETHEUS_METRICS=1.
Exposes /v1/ops/metrics/prometheus as an OpenMetrics scrape target.

Counters:
  lima_requests_total{backend, status}
  lima_backend_errors_total{backend, error_type}
  lima_device_tasks_total{capability, status}
Histograms:
  lima_request_duration_ms{backend}
  lima_backend_latency_ms{backend}
"""

from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)

_TRUE_VALUES = {"1", "true", "yes", "on"}
_HEALTH_STATUSES = ("healthy", "degraded", "dead", "unknown")
_HEALTH_VALUES = {"healthy": 1.0, "degraded": 0.5, "dead": 0.0, "unknown": 0.0}

_registry: Any | None = None
_counters: dict[str, Any] = {}
_histograms: dict[str, Any] = {}
_gauges: dict[str, Any] = {}


def is_enabled() -> bool:
    return os.environ.get("LIMA_PROMETHEUS_METRICS", "0").strip().lower() in _TRUE_VALUES


def _load_client() -> dict[str, Any]:
    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
    except ImportError as exc:
        message = "prometheus_client is required when LIMA_PROMETHEUS_METRICS=1"
        _log.error(message)
        raise RuntimeError(message) from exc
    return {
        "CollectorRegistry": CollectorRegistry,
        "Counter": Counter,
        "Gauge": Gauge,
        "Histogram": Histogram,
        "generate_latest": generate_latest,
    }


def validate_startup() -> None:
    """Fail visibly when metrics are enabled without a working dependency."""
    if not is_enabled():
        return
    _ensure_instruments()


def _ensure_instruments() -> None:
    """Create Prometheus instruments on first use."""
    global _registry
    if not is_enabled() or _registry is not None:
        return

    client = _load_client()
    registry = client["CollectorRegistry"](auto_describe=True)
    counter = client["Counter"]
    gauge = client["Gauge"]
    histogram = client["Histogram"]

    _counters["requests"] = counter(
        "lima_requests_total",
        "Total requests",
        ["backend", "status"],
        registry=registry,
    )
    _counters["backend_errors"] = counter(
        "lima_backend_errors_total",
        "Backend errors",
        ["backend", "error_type"],
        registry=registry,
    )
    _counters["device_tasks"] = counter(
        "lima_device_tasks_total",
        "Device tasks",
        ["capability", "status"],
        registry=registry,
    )
    _histograms["request_duration"] = histogram(
        "lima_request_duration_ms",
        "Request duration",
        ["backend"],
        buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
        registry=registry,
    )
    _histograms["backend_latency"] = histogram(
        "lima_backend_latency_ms",
        "Backend response latency",
        ["backend"],
        buckets=[100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
        registry=registry,
    )
    _gauges["backend_health"] = gauge(
        "lima_backend_health",
        "Backend health status (1=healthy, 0.5=degraded, 0=dead)",
        ["backend", "status"],
        registry=registry,
    )
    _gauges["backend_score"] = gauge(
        "lima_backend_score",
        "Backend health score (0-1)",
        ["backend"],
        registry=registry,
    )
    _registry = registry


def record_request(backend: str, status: str, duration_ms: float) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    c = _counters.get("requests")
    h = _histograms.get("request_duration")
    if c:
        c.labels(backend=backend, status=status).inc()
    if h:
        h.labels(backend=backend).observe(duration_ms)


def record_backend_error(backend: str, error_type: str) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    c = _counters.get("backend_errors")
    if c:
        c.labels(backend=backend, error_type=error_type).inc()


def record_device_task(capability: str, status: str) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    c = _counters.get("device_tasks")
    if c:
        c.labels(capability=capability, status=status).inc()


def record_backend_latency(backend: str, latency_ms: float) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    h = _histograms.get("backend_latency")
    if h:
        h.labels(backend=backend).observe(latency_ms)


def record_backend_health(backend: str, status: str) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    gauge = _gauges.get("backend_health")
    if not gauge:
        return
    normalized = status if status in _HEALTH_STATUSES else "unknown"
    for known_status in _HEALTH_STATUSES:
        value = _HEALTH_VALUES[normalized] if known_status == normalized else 0.0
        gauge.labels(backend=backend, status=known_status).set(value)


def record_backend_score(backend: str, score: float) -> None:
    if not is_enabled():
        return
    _ensure_instruments()
    gauge = _gauges.get("backend_score")
    if gauge:
        gauge.labels(backend=backend).set(max(0.0, min(1.0, float(score))))


def generate_metrics() -> bytes:
    """Generate Prometheus text format output."""
    if not is_enabled():
        return b""
    _ensure_instruments()
    client = _load_client()
    return client["generate_latest"](_registry)
