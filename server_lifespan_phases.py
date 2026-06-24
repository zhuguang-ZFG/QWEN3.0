"""Individual startup/shutdown phase implementations for LiMa lifespan."""

from __future__ import annotations

import logging
from collections.abc import Coroutine
from typing import Callable

import http_caller
import probe_loop
from server_lifespan_state import PhaseTimer

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Critical phases — must complete before /health reports ready/warming.
# ---------------------------------------------------------------------------


async def load_health_state() -> None:
    async with PhaseTimer("health_state.load"):
        try:
            import health_state

            loaded = health_state.load_health_state()
            _log.info("Loaded health state: %d backends", loaded)
        except ImportError as exc:
            _log.warning("health_state module not loaded; persisted health state skipped: %s", exc)


async def load_retired_backends() -> None:
    async with PhaseTimer("backend_retirement.load"):
        try:
            import backend_retirement

            loaded = backend_retirement.load_retired()
            _log.info("Loaded retired backends: %d", loaded)
        except ImportError as exc:
            _log.warning("backend_retirement module not loaded; retired backend state skipped: %s", exc)


async def apply_startup_admission() -> None:
    async with PhaseTimer("backend_admission_store.apply_startup"):
        try:
            from backend_admission_store import apply_startup

            apply_startup()
        except ImportError as exc:
            _log.warning("backend_admission_store not installed; dynamic backend admission skipped: %s", exc)


async def start_probe_loop() -> None:
    async with PhaseTimer("probe_loop.start"):
        probe_loop.start(probe_fn=http_caller.probe)


async def start_device_gateway_runtime() -> None:
    async with PhaseTimer("device_gateway.runtime.start"):
        try:
            from routes.device_gateway_helpers import start_device_gateway_runtime

            await start_device_gateway_runtime()
        except ImportError as exc:
            _log.warning("routes.device_gateway not installed; device gateway runtime skipped: %s", exc)


async def start_mqtt_client() -> None:
    async with PhaseTimer("device_gateway.mqtt_client.start"):
        try:
            from device_gateway.mqtt_client import start_mqtt_client

            await start_mqtt_client()
        except ImportError as exc:
            _log.warning("device_gateway.mqtt_client not installed; MQTT client skipped: %s", exc)


# ---------------------------------------------------------------------------
# Warm phases — may be deferred without blocking request serving.
# ---------------------------------------------------------------------------


async def load_backend_profiles() -> None:
    async with PhaseTimer("backend_profile.load"):
        try:
            import backend_profile

            loaded = backend_profile.load_profiles()
            _log.info("Loaded backend profiles: %d", loaded)
            backend_profile.save_on_interval(300)
        except ImportError as exc:
            _log.warning("backend_profile module not loaded; persisted backend profiles skipped: %s", exc)


async def start_session_memory_daemon() -> None:
    async with PhaseTimer("session_memory.daemon.start"):
        try:
            from session_memory.daemon import start_daemon

            await start_daemon()
        except ImportError as exc:
            _log.warning("session_memory.daemon not installed; session memory daemon skipped: %s", exc)


async def setup_structured_logging() -> None:
    async with PhaseTimer("observability.structured_logging"):
        try:
            from observability.structured_logging import setup_structured_logging

            setup_structured_logging()
        except ImportError as exc:
            _log.warning("observability.structured_logging not installed; structured logging setup skipped: %s", exc)


async def start_auto_indexer() -> None:
    async with PhaseTimer("context_pipeline.auto_indexer.start"):
        try:
            from context_pipeline.auto_indexer import start_auto_indexer

            start_auto_indexer()
        except ImportError as exc:
            _log.warning("context_pipeline.auto_indexer not installed; auto indexer skipped: %s", exc)


async def start_prometheus() -> None:
    async with PhaseTimer("observability.prometheus.start"):
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


# ---------------------------------------------------------------------------
# Shutdown phases.
# ---------------------------------------------------------------------------


def stop_probe_loop() -> None:
    probe_loop.stop()


async def stop_prometheus() -> None:
    try:
        from observability.prometheus_exporter import stop_exporter

        stop_exporter()
    except ImportError as exc:
        _log.warning("prometheus_exporter not installed; prometheus stop skipped: %s", exc)


async def stop_auto_indexer() -> None:
    try:
        from context_pipeline.auto_indexer import stop_auto_indexer

        stop_auto_indexer()
    except ImportError as exc:
        _log.warning("auto_indexer not installed; auto indexer stop skipped: %s", exc)


async def stop_session_memory_daemon() -> None:
    try:
        from session_memory.daemon import stop_daemon

        await stop_daemon()
    except ImportError as exc:
        _log.warning("session_memory.daemon not installed; session memory daemon stop skipped: %s", exc)


async def stop_device_gateway_runtime() -> None:
    try:
        from routes.device_gateway_helpers import stop_device_gateway_runtime

        await stop_device_gateway_runtime()
    except ImportError as exc:
        _log.warning("routes.device_gateway not installed; device gateway runtime stop skipped: %s", exc)


async def stop_mqtt_client() -> None:
    try:
        from device_gateway.mqtt_client import stop_mqtt_client

        await stop_mqtt_client()
    except ImportError as exc:
        _log.warning("device_gateway.mqtt_client not installed; MQTT client stop skipped: %s", exc)


# Expose ordered callables for lifespan orchestration.
_PhaseFn = Callable[[], Coroutine[None, None, None]]

CRITICAL_PHASES: list[_PhaseFn] = [
    load_health_state,
    load_retired_backends,
    apply_startup_admission,
    start_probe_loop,
    start_device_gateway_runtime,
    start_mqtt_client,
]

WARM_PHASES: list[tuple[str, _PhaseFn]] = [
    ("backend_profile.load", load_backend_profiles),
    ("session_memory.daemon.start", start_session_memory_daemon),
    ("observability.structured_logging", setup_structured_logging),
    ("context_pipeline.auto_indexer.start", start_auto_indexer),
    ("observability.prometheus.start", start_prometheus),
]
