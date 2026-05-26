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

_log = logging.getLogger(__name__)

_ENABLED = os.environ.get("LIMA_PROMETHEUS_METRICS", "0").strip().lower() in {
    "1", "true", "yes",
}

# Lazy-import prometheus_client to avoid hard dependency
_counters: dict[str, object] = {}
_histograms: dict[str, object] = {}


def _ensure_instruments():
    """Create Prometheus instruments on first use."""
    if _counters or not _ENABLED:
        return
    try:
        from prometheus_client import Counter, Histogram, generate_latest, REGISTRY  # noqa: F401

        _counters["requests"] = Counter(
            "lima_requests_total", "Total requests", ["backend", "status"],
        )
        _counters["backend_errors"] = Counter(
            "lima_backend_errors_total", "Backend errors", ["backend", "error_type"],
        )
        _counters["device_tasks"] = Counter(
            "lima_device_tasks_total", "Device tasks", ["capability", "status"],
        )
        _histograms["request_duration"] = Histogram(
            "lima_request_duration_ms", "Request duration",
            ["backend"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000],
        )
        _histograms["backend_latency"] = Histogram(
            "lima_backend_latency_ms", "Backend response latency",
            ["backend"],
            buckets=[100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
        )
    except ImportError:
        _log.debug("prometheus_client not installed")
    except Exception:
        _log.debug("Prometheus instrument init failed", exc_info=True)


def is_enabled() -> bool:
    return _ENABLED


def record_request(backend: str, status: str, duration_ms: float) -> None:
    _ensure_instruments()
    c = _counters.get("requests")
    h = _histograms.get("request_duration")
    if c:
        c.labels(backend=backend, status=status).inc()
    if h:
        h.labels(backend=backend).observe(duration_ms)


def record_backend_error(backend: str, error_type: str) -> None:
    _ensure_instruments()
    c = _counters.get("backend_errors")
    if c:
        c.labels(backend=backend, error_type=error_type).inc()


def record_device_task(capability: str, status: str) -> None:
    _ensure_instruments()
    c = _counters.get("device_tasks")
    if c:
        c.labels(capability=capability, status=status).inc()


def record_backend_latency(backend: str, latency_ms: float) -> None:
    _ensure_instruments()
    h = _histograms.get("backend_latency")
    if h:
        h.labels(backend=backend).observe(latency_ms)


def generate_metrics() -> bytes:
    """Generate Prometheus text format output."""
    _ensure_instruments()
    try:
        from prometheus_client import generate_latest  # noqa: F811

        return generate_latest()
    except ImportError:
        return b"# prometheus_client not installed\n"
