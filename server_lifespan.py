"""FastAPI lifespan orchestration for LiMa Server."""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import http_caller
import probe_loop
from channel_retirement import retire_telegram_webhook_from_env

_log = logging.getLogger(__name__)

STARTUP_PHASES: list[dict[str, Any]] = []


def _record_phase(name: str, elapsed_ms: float, status: str = "ok", detail: str = "") -> None:
    phase = {
        "name": name,
        "elapsed_ms": round(elapsed_ms, 1),
        "status": status,
        "detail": detail,
    }
    STARTUP_PHASES.append(phase)
    _log.warning("[LIFESPAN] phase=%s elapsed_ms=%.1f status=%s %s", name, elapsed_ms, status, detail)


class _phase:
    """Context manager that records elapsed time for a lifespan phase."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.started = 0.0

    async def __aenter__(self):
        self.started = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        elapsed_ms = (time.perf_counter() - self.started) * 1000
        status = "error" if exc else "ok"
        detail = f"{exc}" if exc else ""
        _record_phase(self.name, elapsed_ms, status, detail)


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    STARTUP_PHASES.clear()

    async with _phase("health_state.load"):
        try:
            import health_state
            loaded = health_state.load_health_state()
            _log.info("Loaded health state: %d backends", loaded)
        except ImportError as exc:
            _log.warning("health_state module not loaded; persisted health state skipped: %s", exc)

    async with _phase("backend_profile.load"):
        try:
            import backend_profile
            loaded = backend_profile.load_profiles()
            _log.info("Loaded backend profiles: %d", loaded)
            backend_profile.save_on_interval(300)
        except ImportError as exc:
            _log.warning("backend_profile module not loaded; persisted backend profiles skipped: %s", exc)

    async with _phase("backend_retirement.load"):
        try:
            import backend_retirement
            loaded = backend_retirement.load_retired()
            _log.info("Loaded retired backends: %d", loaded)
        except ImportError as exc:
            _log.warning("backend_retirement module not loaded; retired backend state skipped: %s", exc)

    async with _phase("backend_admission_store.apply_startup"):
        try:
            from backend_admission_store import apply_startup

            apply_startup()
        except ImportError:
            _log.debug("backend_admission_store not installed")

    async with _phase("probe_loop.start"):
        probe_loop.start(probe_fn=http_caller.probe)

    async with _phase("periodic_coding_eval.start"):
        try:
            import periodic_coding_eval

            periodic_coding_eval.start()
        except ImportError:
            _log.debug("periodic_coding_eval not installed")

    async with _phase("session_memory.daemon.start"):
        try:
            from session_memory.daemon import start_daemon

            await start_daemon()
        except ImportError:
            _log.debug("session_memory.daemon not installed")

    async with _phase("channel_retirement.telegram"):
        await retire_telegram_webhook_from_env()

    async with _phase("device_gateway.runtime.start"):
        try:
            from routes.device_gateway import start_device_gateway_runtime

            await start_device_gateway_runtime()
        except ImportError:
            _log.debug("routes.device_gateway runtime not installed")

    async with _phase("observability.structured_logging"):
        try:
            from observability.structured_logging import setup_structured_logging

            setup_structured_logging()
        except ImportError:
            _log.debug("observability.structured_logging not installed")

    async with _phase("device_gateway.mqtt_client.start"):
        try:
            from device_gateway.mqtt_client import start_mqtt_client

            await start_mqtt_client()
        except ImportError:
            _log.debug("device_gateway.mqtt_client not installed")

    async with _phase("context_pipeline.auto_indexer.start"):
        try:
            from context_pipeline.auto_indexer import start_auto_indexer

            start_auto_indexer()
        except ImportError:
            _log.debug("auto_indexer not installed")

    async with _phase("observability.prometheus.start"):
        try:
            from observability.prometheus_metrics import validate_startup
            from observability.prometheus_exporter import start_exporter

            validate_startup()
            start_exporter()
        except ImportError as exc:
            _log.warning("prometheus metrics modules not loaded; metrics exporter skipped: %s", exc)
        except RuntimeError as exc:
            _log.error("prometheus metrics startup validation failed: %s", exc)
            raise
    try:
        yield
    finally:
        probe_loop.stop()
        try:
            from observability.prometheus_exporter import stop_exporter

            stop_exporter()
        except ImportError:
            _log.debug("prometheus_exporter stop skipped")
        try:
            from context_pipeline.auto_indexer import stop_auto_indexer

            stop_auto_indexer()
        except ImportError as exc:
            _log.debug("auto_indexer stop skipped; module not loaded: %s", exc)
        try:
            import periodic_coding_eval

            periodic_coding_eval.stop()
        except ImportError:
            _log.debug("periodic_coding_eval stop skipped")
        try:
            from session_memory.daemon import stop_daemon

            await stop_daemon()
        except ImportError:
            _log.debug("session_memory.daemon stop skipped")
        try:
            from routes.device_gateway import stop_device_gateway_runtime

            await stop_device_gateway_runtime()
        except ImportError:
            _log.debug("device_gateway runtime stop skipped")
        try:
            from device_gateway.mqtt_client import stop_mqtt_client

            await stop_mqtt_client()
        except ImportError:
            _log.debug("mqtt_client stop skipped")
