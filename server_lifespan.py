"""FastAPI lifespan orchestration for LiMa Server."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import http_caller
import probe_loop
from channel_retirement import retire_telegram_webhook_from_env

_log = logging.getLogger(__name__)

STARTUP_PHASES: list[dict[str, Any]] = []

# Public startup state for /health and observability.
# status: "starting" | "ready" | "warming" | "error"
_startup_state: dict[str, Any] = {
    "status": "starting",
    "critical_done": False,
    "pending_warm": [],
    "errors": [],
}


def get_startup_state() -> dict[str, Any]:
    """Return a snapshot of the current startup state."""
    return {
        "status": _startup_state["status"],
        "critical_done": _startup_state["critical_done"],
        "pending_warm": list(_startup_state["pending_warm"]),
        "errors": list(_startup_state["errors"]),
    }


def _set_status(status: str) -> None:
    _startup_state["status"] = status
    _log.warning("[LIFESPAN] startup_status=%s", status)


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


async def _load_health_state() -> None:
    async with _phase("health_state.load"):
        try:
            import health_state

            loaded = health_state.load_health_state()
            _log.info("Loaded health state: %d backends", loaded)
        except ImportError as exc:
            _log.warning("health_state module not loaded; persisted health state skipped: %s", exc)


async def _load_retired_backends() -> None:
    async with _phase("backend_retirement.load"):
        try:
            import backend_retirement

            loaded = backend_retirement.load_retired()
            _log.info("Loaded retired backends: %d", loaded)
        except ImportError as exc:
            _log.warning("backend_retirement module not loaded; retired backend state skipped: %s", exc)


async def _apply_startup_admission() -> None:
    async with _phase("backend_admission_store.apply_startup"):
        try:
            from backend_admission_store import apply_startup

            apply_startup()
        except ImportError as exc:
            _log.warning("backend_admission_store not installed; dynamic backend admission skipped: %s", exc)


async def _start_probe_loop() -> None:
    async with _phase("probe_loop.start"):
        probe_loop.start(probe_fn=http_caller.probe)


async def _start_device_gateway_runtime() -> None:
    async with _phase("device_gateway.runtime.start"):
        try:
            from routes.device_gateway import start_device_gateway_runtime

            await start_device_gateway_runtime()
        except ImportError as exc:
            _log.warning("routes.device_gateway not installed; device gateway runtime skipped: %s", exc)


async def _start_mqtt_client() -> None:
    async with _phase("device_gateway.mqtt_client.start"):
        try:
            from device_gateway.mqtt_client import start_mqtt_client

            await start_mqtt_client()
        except ImportError as exc:
            _log.warning("device_gateway.mqtt_client not installed; MQTT client skipped: %s", exc)


# ---------------------------------------------------------------------------
# Warm phases — may be deferred without blocking request serving.
# ---------------------------------------------------------------------------


async def _load_backend_profiles() -> None:
    async with _phase("backend_profile.load"):
        try:
            import backend_profile

            loaded = backend_profile.load_profiles()
            _log.info("Loaded backend profiles: %d", loaded)
            backend_profile.save_on_interval(300)
        except ImportError as exc:
            _log.warning("backend_profile module not loaded; persisted backend profiles skipped: %s", exc)


async def _start_periodic_eval() -> None:
    async with _phase("periodic_coding_eval.start"):
        try:
            import periodic_coding_eval

            periodic_coding_eval.start()
        except ImportError as exc:
            _log.warning("periodic_coding_eval not installed; periodic coding eval skipped: %s", exc)


async def _start_session_memory_daemon() -> None:
    async with _phase("session_memory.daemon.start"):
        try:
            from session_memory.daemon import start_daemon

            await start_daemon()
        except ImportError as exc:
            _log.warning("session_memory.daemon not installed; session memory daemon skipped: %s", exc)


async def _schedule_telegram_retirement() -> None:
    async with _phase("channel_retirement.telegram"):
        try:
            asyncio.create_task(retire_telegram_webhook_from_env())
        except Exception as exc:
            _log.debug("telegram webhook cleanup scheduling failed: %s", type(exc).__name__)


async def _setup_structured_logging() -> None:
    async with _phase("observability.structured_logging"):
        try:
            from observability.structured_logging import setup_structured_logging

            setup_structured_logging()
        except ImportError as exc:
            _log.warning("observability.structured_logging not installed; structured logging setup skipped: %s", exc)


async def _start_auto_indexer() -> None:
    async with _phase("context_pipeline.auto_indexer.start"):
        try:
            from context_pipeline.auto_indexer import start_auto_indexer

            start_auto_indexer()
        except ImportError as exc:
            _log.warning("context_pipeline.auto_indexer not installed; auto indexer skipped: %s", exc)


async def _start_prometheus() -> None:
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


async def _run_warm_phase(name: str, coro) -> None:
    """Run a warm phase and track its completion."""
    _startup_state["pending_warm"].append(name)
    try:
        await coro
    except Exception as exc:
        _log.warning("[LIFESPAN] warm phase %s failed: %s", name, exc, exc_info=True)
        _startup_state["errors"].append(f"{name}: {exc}")
    finally:
        _startup_state["pending_warm"].remove(name)
        if not _startup_state["pending_warm"] and _startup_state["critical_done"]:
            _set_status("ready")


async def _run_startup_phases() -> None:
    """Execute critical phases sequentially, then kick off warm phases."""
    _startup_state["status"] = "starting"
    _startup_state["critical_done"] = False
    _startup_state["pending_warm"].clear()
    _startup_state["errors"].clear()

    critical = [
        _load_health_state,
        _load_retired_backends,
        _apply_startup_admission,
        _start_probe_loop,
        _start_device_gateway_runtime,
        _start_mqtt_client,
    ]

    for phase_fn in critical:
        try:
            await phase_fn()
        except Exception as exc:
            _log.error("[LIFESPAN] critical phase %s failed: %s", phase_fn.__name__, exc, exc_info=True)
            _startup_state["errors"].append(f"{phase_fn.__name__}: {exc}")
            _set_status("error")
            return

    _startup_state["critical_done"] = True
    _set_status("warming")

    warm = [
        ("backend_profile.load", _load_backend_profiles),
        ("periodic_coding_eval.start", _start_periodic_eval),
        ("session_memory.daemon.start", _start_session_memory_daemon),
        ("channel_retirement.telegram", _schedule_telegram_retirement),
        ("observability.structured_logging", _setup_structured_logging),
        ("context_pipeline.auto_indexer.start", _start_auto_indexer),
        ("observability.prometheus.start", _start_prometheus),
    ]

    for name, phase_fn in warm:
        asyncio.create_task(_run_warm_phase(name, phase_fn()))


async def _stop_prometheus() -> None:
    try:
        from observability.prometheus_exporter import stop_exporter

        stop_exporter()
    except ImportError as exc:
        _log.warning("prometheus_exporter not installed; prometheus stop skipped: %s", exc)


async def _stop_auto_indexer() -> None:
    try:
        from context_pipeline.auto_indexer import stop_auto_indexer

        stop_auto_indexer()
    except ImportError as exc:
        _log.warning("auto_indexer not installed; auto indexer stop skipped: %s", exc)


async def _stop_periodic_eval() -> None:
    try:
        import periodic_coding_eval

        periodic_coding_eval.stop()
    except ImportError as exc:
        _log.warning("periodic_coding_eval not installed; periodic eval stop skipped: %s", exc)


async def _stop_session_memory_daemon() -> None:
    try:
        from session_memory.daemon import stop_daemon

        await stop_daemon()
    except ImportError as exc:
        _log.warning("session_memory.daemon not installed; session memory daemon stop skipped: %s", exc)


async def _stop_device_gateway_runtime() -> None:
    try:
        from routes.device_gateway import stop_device_gateway_runtime

        await stop_device_gateway_runtime()
    except ImportError as exc:
        _log.warning("routes.device_gateway not installed; device gateway runtime stop skipped: %s", exc)


async def _stop_mqtt_client() -> None:
    try:
        from device_gateway.mqtt_client import stop_mqtt_client

        await stop_mqtt_client()
    except ImportError as exc:
        _log.warning("device_gateway.mqtt_client not installed; MQTT client stop skipped: %s", exc)


async def _run_shutdown_phases() -> None:
    """Execute all shutdown phases sequentially."""
    probe_loop.stop()
    await _stop_prometheus()
    await _stop_auto_indexer()
    await _stop_periodic_eval()
    await _stop_session_memory_daemon()
    await _stop_device_gateway_runtime()
    await _stop_mqtt_client()


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    STARTUP_PHASES.clear()
    await _run_startup_phases()
    try:
        yield
    finally:
        await _run_shutdown_phases()
