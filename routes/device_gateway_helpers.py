"""Helpers for routes/device_gateway.py — keep the route file under 300 lines."""

from __future__ import annotations

from typing import Any

from device_intelligence.shadow import shadow_store
from device_gateway.sessions import registry
from device_gateway.store import configure_task_store_from_env
from device_ledger.store import configure_ledger_store_from_env
from device_memory.store import configure_memory_store_from_env
from device_gateway.notifier import (
    configure_notifier_from_env,
    start_task_notifier,
    stop_task_notifier,
)
from device_gateway.tasks import reset_tasks_for_tests
from routes.device_gateway_dispatch import notify_local_session_task_available


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


async def start_device_gateway_runtime() -> None:
    configure_task_store_from_env()
    configure_memory_store_from_env()
    configure_ledger_store_from_env()
    configure_notifier_from_env()
    await start_task_notifier(notify_local_session_task_available)


async def stop_device_gateway_runtime() -> None:
    await stop_task_notifier()


def _reset_for_tests() -> None:
    registry.clear()
    reset_tasks_for_tests()
    shadow_store.reset()
