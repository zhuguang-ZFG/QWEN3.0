"""Prometheus metrics endpoint for LiMa.

Enabled via LIMA_PROMETHEUS_METRICS=1.
Exposes /v1/ops/metrics/prometheus as an OpenMetrics scrape target.

Counters:
  lima_requests_total{backend, status}
  lima_backend_errors_total{backend, error_type}
  lima_backend_retirement_events_total{backend}
  lima_device_tasks_total{capability, status}
Histograms:
  lima_request_duration_ms{backend}
  lima_backend_latency_ms{backend}
Gauges:
  lima_backend_retired{backend}
  lima_backend_retired_count
"""

from __future__ import annotations

import logging
from typing import Any

from config import settings

_log = logging.getLogger(__name__)

_HEALTH_STATUSES = ("healthy", "degraded", "dead", "unknown")
_HEALTH_VALUES = {"healthy": 1.0, "degraded": 0.5, "dead": 0.0, "unknown": 0.0}

_STARTUP_STATUS_VALUES = {"ready": 1.0, "warming": 0.5, "starting": 0.0, "error": 0.0}

_registry: Any | None = None
_counters: dict[str, Any] = {}
_histograms: dict[str, Any] = {}
_gauges: dict[str, Any] = {}
_retired_backend_labels: set[str] = set()


def is_enabled() -> bool:
    return settings.OBSERVABILITY.prometheus_metrics


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
    _register_counters(client["Counter"], registry)
    _register_histograms(client["Histogram"], registry)
    _register_gauges(client["Gauge"], registry)
    _registry = registry


def _register_counters(counter, registry) -> None:
    _counters["requests"] = counter("lima_requests_total", "Total requests", ["backend", "status"], registry=registry)
    _counters["backend_errors"] = counter(
        "lima_backend_errors_total", "Backend errors", ["backend", "error_type"], registry=registry
    )
    _counters["device_tasks"] = counter(
        "lima_device_tasks_total", "Device tasks", ["capability", "status"], registry=registry
    )
    _counters["backend_retirement_events"] = counter(
        "lima_backend_retirement_events_total",
        "Backend retirement events applied",
        ["backend"],
        registry=registry,
    )
    _counters["image_cache_lookups"] = counter(
        "lima_image_cache_lookups_total",
        "Image cache lookups by result",
        ["result"],
        registry=registry,
    )
    _counters["image_requests"] = counter(
        "lima_image_requests_total",
        "Image generation requests by backend",
        ["backend"],
        registry=registry,
    )
    _counters["handwriting_requests"] = counter(
        "lima_handwriting_requests_total",
        "Handwriting requests by final status",
        ["status", "fallback"],
        registry=registry,
    )


def _register_histograms(histogram, registry) -> None:
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
    _histograms["startup_phase_duration"] = histogram(
        "lima_startup_phase_duration_ms",
        "Startup phase duration in milliseconds",
        ["phase"],
        buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
        registry=registry,
    )
    _histograms["handwriting_duration"] = histogram(
        "lima_handwriting_duration_ms",
        "Handwriting request duration in milliseconds",
        ["status"],
        buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
        registry=registry,
    )


def _register_gauges(gauge, registry) -> None:
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
    _gauges["backend_retired"] = gauge(
        "lima_backend_retired",
        "Backend manually retired from routing pools (1=retired, 0=active)",
        ["backend"],
        registry=registry,
    )
    _gauges["backend_retired_count"] = gauge(
        "lima_backend_retired_count",
        "Count of backends currently retired",
        registry=registry,
    )
    _gauges["startup_status"] = gauge(
        "lima_startup_status",
        "Startup status: 1=ready, 0.5=warming, 0=starting/error",
        registry=registry,
    )
    _gauges["image_cache_entries"] = gauge(
        "lima_image_cache_entries",
        "Current number of cached image generation entries",
        registry=registry,
    )
    _gauges["device_tasks_pending"] = gauge(
        "lima_device_tasks_pending_total",
        "Current number of device tasks pending dispatch",
        registry=registry,
    )


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


# Re-export focused submodule helpers so this file stays under the project size limit
# while keeping the public API unchanged.  F401 suppressed — these are deliberate
# re-exports consumed by callers that do `from observability import prometheus_metrics`.
from observability.prometheus_device_task_metrics import (  # noqa: E402,F401
    record_device_task_dead_letter,
    record_device_task_dispatch_failure,
    record_device_task_dispatched,
    record_device_task_issued,
    record_device_task_retry,
    set_device_tasks_pending,
)
from observability.prometheus_handwriting_metrics import (  # noqa: E402,F401
    record_handwriting_duration,
    record_handwriting_request,
)
from observability.prometheus_image_metrics import (  # noqa: E402,F401
    record_image_cache_entries,
    record_image_cache_lookup,
    record_image_request,
)
from observability.prometheus_startup_metrics import (  # noqa: E402,F401
    record_backend_retirement_event,
    record_startup_phase,
    record_startup_status,
    sync_retired_backends,
)
