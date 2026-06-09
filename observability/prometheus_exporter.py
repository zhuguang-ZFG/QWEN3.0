"""Prometheus metrics exporter background task.

Periodically updates Gauge metrics that reflect system state:
- lima_backend_health{backend, status}
- lima_backend_score{backend}
"""

from __future__ import annotations

import logging
import threading
import time

_log = logging.getLogger(__name__)

_exporter_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _export_loop():
    """Background thread that updates Prometheus Gauge metrics."""
    from observability.prometheus_metrics import is_enabled

    if not is_enabled():
        _log.debug("Prometheus metrics disabled, exporter thread exiting")
        return

    try:
        from prometheus_client import Gauge
    except ImportError:
        _log.debug("prometheus_client not installed, exporter thread exiting")
        return

    # Create Gauge instruments
    backend_health_gauge = Gauge(
        "lima_backend_health",
        "Backend health status (1=healthy, 0.5=degraded, 0=dead)",
        ["backend", "status"],
    )
    backend_score_gauge = Gauge(
        "lima_backend_score",
        "Backend health score (0-1)",
        ["backend"],
    )

    _log.info("Prometheus exporter thread started")

    while not _stop_event.is_set():
        try:
            # Update backend health gauges
            import health_tracker

            health_map = health_tracker.get_health_map()
            scores = health_tracker.get_scores()

            for backend, status in health_map.items():
                # Set health value
                if status == "healthy":
                    value = 1.0
                elif status == "degraded":
                    value = 0.5
                elif status == "dead":
                    value = 0.0
                else:
                    value = 0.0

                backend_health_gauge.labels(backend=backend, status=status).set(value)

                # Set score gauge
                score = scores.get(backend, 0.0)
                backend_score_gauge.labels(backend=backend).set(score)

        except Exception as exc:
            _log.debug("Prometheus gauge update failed: %s", type(exc).__name__, exc_info=True)

        # Sleep for 30 seconds or until stop event
        _stop_event.wait(timeout=30.0)

    _log.info("Prometheus exporter thread stopped")


def start_exporter():
    """Start the background metrics exporter thread."""
    global _exporter_thread

    from observability.prometheus_metrics import is_enabled

    if not is_enabled():
        _log.debug("Prometheus metrics disabled, not starting exporter")
        return

    if _exporter_thread is not None and _exporter_thread.is_alive():
        _log.debug("Prometheus exporter thread already running")
        return

    _stop_event.clear()
    _exporter_thread = threading.Thread(target=_export_loop, daemon=True, name="PrometheusExporter")
    _exporter_thread.start()
    _log.info("Prometheus exporter thread launched")


def stop_exporter():
    """Stop the background metrics exporter thread."""
    global _exporter_thread

    if _exporter_thread is None or not _exporter_thread.is_alive():
        return

    _stop_event.set()
    _exporter_thread.join(timeout=5.0)
    _exporter_thread = None
    _log.info("Prometheus exporter thread stopped")
