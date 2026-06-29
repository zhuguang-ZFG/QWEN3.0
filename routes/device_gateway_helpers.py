"""Helpers for routes/device_gateway.py — keep the route file under 300 lines."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from device_intelligence.shadow import shadow_store
from device_gateway.sessions import registry
from device_gateway.store import configure_task_store_from_env
from device_gateway.task_lifecycle import recover_stale_processing
from device_ledger.store import configure_ledger_store_from_env
from device_memory.store import configure_memory_store_from_env
from device_gateway.notifier import (
    configure_notifier_from_env,
    start_task_notifier,
    stop_task_notifier,
)
from device_gateway.tasks import reset_tasks_for_tests
from routes.device_gateway_dispatch import notify_local_session_task_available

logger = logging.getLogger(__name__)

# AUDIT-4-F2：卡在 processing 队列的僵尸任务回收周期。
# 设备在 LMOVE（pending→processing）后、ack 前崩溃则任务永远卡 processing。
# reaper 周期性扫描已连接设备的 processing 队列，把超时任务塞回 pending。
_REAPER_INTERVAL_SECONDS = 60.0
_REAPER_STALE_SECONDS = 120.0
_reaper_task: asyncio.Task[None] | None = None


def _record_device_task_evidence(
    *,
    device_id: str,
    task: dict[str, Any],
    status: str,
    request_id: str = "",
) -> None:
    from observability.capability_evidence import record_evidence_safe

    record_evidence_safe(
        loop="device_gateway",
        request_id=request_id or str(task.get("request_id", "")),
        task_id=str(task.get("task_id", "")),
        device_id=device_id,
        entrypoint="/device/v1/tasks",
        status=status,
        evidence=["device_task_created"],
        rollback="delete pending task queue for test device if smoke-generated",
    )


async def _stale_task_reaper_loop() -> None:
    """Periodically recover tasks stuck in processing queues (AUDIT-4-F2).

    扫描已连接设备（registry 中有活跃会话的设备），把卡在 processing
    超过 _REAPER_STALE_SECONDS 的任务重新塞回 pending 队列，避免丢任务。
    """
    while True:
        try:
            await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
            device_ids = list(registry.active_device_ids())
            for device_id in device_ids:
                try:
                    recovered = recover_stale_processing(device_id, _REAPER_STALE_SECONDS)
                    if recovered:
                        logger.info("stale task reaper recovered %d tasks for device=%s", recovered, device_id)
                        await notify_local_session_task_available(device_id)
                except Exception as exc:
                    logger.debug("reaper skip device=%s: %s", device_id, exc)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("stale task reaper iteration failed: %s", exc, exc_info=True)


async def start_device_gateway_runtime() -> None:
    global _reaper_task
    configure_task_store_from_env()
    configure_memory_store_from_env()
    configure_ledger_store_from_env()
    configure_notifier_from_env()
    await start_task_notifier(notify_local_session_task_available)
    _reaper_task = asyncio.create_task(_stale_task_reaper_loop())


async def stop_device_gateway_runtime() -> None:
    global _reaper_task
    if _reaper_task is not None and not _reaper_task.done():
        _reaper_task.cancel()
        try:
            await _reaper_task
        except (asyncio.CancelledError, Exception):
            pass
        _reaper_task = None
    await stop_task_notifier()


def _reset_for_tests() -> None:
    registry.clear()
    reset_tasks_for_tests()
    shadow_store.reset()
