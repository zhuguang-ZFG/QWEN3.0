"""Task dispatch facade for DLC core."""

from __future__ import annotations

import asyncio
from typing import Any

from device_gateway.tasks import (
    DeviceTaskRequest,
    active_tasks_for_device,
    create_and_route_task,
)

_dispatch_locks: dict[str, asyncio.Lock] = {}


def _get_lock(device_id: str) -> asyncio.Lock:
    lock = _dispatch_locks.get(device_id)
    if lock is None:
        lock = asyncio.Lock()
        _dispatch_locks[device_id] = lock
    return lock


async def dispatch_task(device_id: str, task: dict[str, Any], *, channel: str = "mqtt") -> dict[str, Any]:
    """Dispatch a task to a device with a busy pre-check.

    Args:
        device_id: target device identifier.
        task: motion_task payload.
        channel: reserved for future transport selection (mqtt/ws).

    Returns:
        {"status": "sent" | "queued" | "queued_no_delivery" | "rejected" | "failed",
         "task_id": str | None, "queue_depth": int, "error": str | None}
    """
    async with _get_lock(device_id):
        if active_tasks_for_device(device_id):
            return {
                "status": "rejected",
                "task_id": None,
                "queue_depth": 0,
                "error": "device_busy",
            }

        # Reuse the existing task routing pipeline.
        text = task.get("text", "")
        request_id = task.get("request_id")
        source = task.get("source", "dlc_api")
        entrypoint = task.get("entrypoint", "")

        result = await create_and_route_task(
            DeviceTaskRequest(
                device_id=device_id,
                text=text,
                request_id=request_id or "",
                source=source,
                entrypoint=entrypoint,
            )
        )

        raw_task = result.task
        return {
            "status": result.status,
            "task_id": str(raw_task.get("task_id")) if raw_task.get("task_id") is not None else None,
            "queue_depth": result.queue_depth,
            "error": str(raw_task.get("error")) if raw_task.get("error") else None,
        }
