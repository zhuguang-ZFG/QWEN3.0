"""FastAPI lifespan orchestration for LiMa Server."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from server_lifespan_phases import (
    CRITICAL_PHASES,
    WARM_PHASES,
    stop_auto_indexer,
    stop_device_gateway_runtime,
    stop_mqtt_client,
    stop_periodic_eval,
    stop_prometheus,
    stop_probe_loop,
    stop_session_memory_daemon,
)
from server_lifespan_state import (
    STARTUP_PHASES,
    add_pending_warm,
    get_startup_state,
    has_pending_warm,
    is_critical_done,
    mark_critical_done,
    record_startup_error,
    remove_pending_warm,
    reset_startup_state,
    set_startup_status,
)

__all__ = ["lifespan", "STARTUP_PHASES", "get_startup_state"]


async def _run_warm_phase(name: str, coro) -> None:
    """Run a warm phase and track its completion."""
    add_pending_warm(name)
    try:
        await coro
    except Exception as exc:
        # Warm phases are best-effort; log but do not fail startup.
        import logging

        logging.getLogger(__name__).warning("[LIFESPAN] warm phase %s failed: %s", name, exc, exc_info=True)
        record_startup_error(name, exc)
    finally:
        remove_pending_warm(name)
        if is_critical_done() and not has_pending_warm():
            set_startup_status("ready")


async def _run_startup_phases() -> None:
    """Execute critical phases sequentially, then kick off warm phases."""
    reset_startup_state()
    set_startup_status("starting")

    for phase_fn in CRITICAL_PHASES:
        try:
            await phase_fn()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error(
                "[LIFESPAN] critical phase %s failed: %s", phase_fn.__name__, exc, exc_info=True
            )
            record_startup_error(phase_fn.__name__, exc)
            set_startup_status("error")
            return

    mark_critical_done()
    set_startup_status("warming")

    for name, phase_fn in WARM_PHASES:
        asyncio.create_task(_run_warm_phase(name, phase_fn()))


async def _run_shutdown_phases() -> None:
    """Execute all shutdown phases sequentially."""
    stop_probe_loop()
    await stop_prometheus()
    await stop_auto_indexer()
    await stop_periodic_eval()
    await stop_session_memory_daemon()
    await stop_device_gateway_runtime()
    await stop_mqtt_client()


@asynccontextmanager
async def lifespan(application):
    """Start and stop background runtime helpers."""
    STARTUP_PHASES.clear()
    await _run_startup_phases()
    try:
        yield
    finally:
        await _run_shutdown_phases()
