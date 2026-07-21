"""M2 background reapers: stale processing + zombie device sessions."""

from __future__ import annotations

import asyncio
import logging

from device_gateway.sessions import registry
from device_gateway.task_lifecycle import recover_stale_processing

_log = logging.getLogger(__name__)

_REAPER_INTERVAL_SECONDS = 60.0
_REAPER_STALE_SECONDS = 120.0
_ZOMBIE_HEARTBEAT_TIMEOUT_SECONDS = 90.0
_ZOMBIE_REAPER_INTERVAL_SECONDS = 30.0

_stale_task: asyncio.Task[None] | None = None
_zombie_task: asyncio.Task[None] | None = None


async def _stale_processing_loop() -> None:
    """Recover tasks stuck in processing; re-push if device still online."""
    while True:
        try:
            await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
            for device_id in list(registry.active_device_ids()):
                try:
                    recovered = await asyncio.to_thread(recover_stale_processing, device_id, _REAPER_STALE_SECONDS)
                    if recovered:
                        _log.info(
                            "stale processing reaper recovered %d task(s) device=%s",
                            recovered,
                            device_id,
                        )
                        from routes.device_gateway_dispatch import try_deliver_pending

                        await try_deliver_pending(device_id)
                except Exception as exc:
                    _log.debug("stale reaper skip device=%s: %s", device_id, exc)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.warning("stale processing reaper failed: %s", exc, exc_info=True)


async def _zombie_session_loop() -> None:
    """Evict sessions with no heartbeat; requeue in-flight tasks."""
    while True:
        try:
            await asyncio.sleep(_ZOMBIE_REAPER_INTERVAL_SECONDS)
            removed = registry.remove_zombies(_ZOMBIE_HEARTBEAT_TIMEOUT_SECONDS)
            for session in removed:
                _log.info("zombie session evicted device=%s", session.device_id)
                try:
                    await session.websocket.close()
                except Exception:
                    _log.debug(
                        "websocket close failed for zombie device=%s",
                        session.device_id,
                        exc_info=True,
                    )
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _log.warning("zombie session reaper failed: %s", exc, exc_info=True)


def reapers_running() -> bool:
    """True when both stale-processing and zombie-session loops are alive."""
    return _stale_task is not None and not _stale_task.done() and _zombie_task is not None and not _zombie_task.done()


async def start_delivery_reapers() -> None:
    global _stale_task, _zombie_task
    if _stale_task is None or _stale_task.done():
        _stale_task = asyncio.create_task(_stale_processing_loop())
    if _zombie_task is None or _zombie_task.done():
        _zombie_task = asyncio.create_task(_zombie_session_loop())
    if not reapers_running():
        raise RuntimeError("delivery reapers failed to start (tasks not running)")
    _log.info("device delivery reapers started (stale processing + zombie sessions)")


async def stop_delivery_reapers() -> None:
    global _stale_task, _zombie_task
    for task in (_stale_task, _zombie_task):
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _stale_task = None
    _zombie_task = None
