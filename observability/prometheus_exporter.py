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
    from observability import prometheus_metrics

    if not prometheus_metrics.is_enabled():
        _log.debug("Prometheus metrics disabled, exporter thread exiting")
        return

    try:
        prometheus_metrics.validate_startup()
    except RuntimeError:
        _log.error("Prometheus exporter cannot start because metrics validation failed", exc_info=True)
        return

    _log.info("Prometheus exporter thread started")

    while not _stop_event.is_set():
        try:
            # Update backend health gauges
            import health_tracker

            health_map = health_tracker.get_health_map()
            scores = health_tracker.get_scores()

            for backend, status in health_map.items():
                prometheus_metrics.record_backend_health(backend, str(status))
                prometheus_metrics.record_backend_score(backend, float(scores.get(backend, 0.0)))

        except ImportError as exc:
            _log.warning("Prometheus gauge update skipped; health_tracker unavailable: %s", exc)
            return
        except Exception as exc:
            _log.warning("Prometheus gauge update failed: %s", type(exc).__name__, exc_info=True)

        # Sleep for 30 seconds or until stop event
        _stop_event.wait(timeout=30.0)

    _log.info("Prometheus exporter thread stopped")


def start_exporter():
    """Start the background metrics exporter thread."""
    global _exporter_thread

    from observability import prometheus_metrics

    if not prometheus_metrics.is_enabled():
        _log.debug("Prometheus metrics disabled, not starting exporter")
        return
    prometheus_metrics.validate_startup()

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
