"""Stable device task creation and routing interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from device_gateway.sessions import registry
from device_gateway.tasks import create_task_from_transcript, enqueue_pending_task, pending_count
from routes.device_gateway_dispatch import dispatch_task_to_session, publish_task_available_safe


@dataclass(frozen=True)
class DeviceTaskRequest:
    device_id: str
    text: str
    request_id: str = ""


@dataclass(frozen=True)
class DeviceTaskRouteResult:
    status: str
    sent: bool
    queue_depth: int
    task: dict[str, Any]


async def create_and_route_task(request: DeviceTaskRequest) -> DeviceTaskRouteResult:
    """Create a motion task, then dispatch locally or enqueue for the device."""
    device_id = request.device_id.strip()
    text = request.text.strip()
    task = create_task_from_transcript(
        device_id,
        text,
        request_id=request.request_id or None,
    )
    if task.get("error"):
        return DeviceTaskRouteResult("failed", False, pending_count(device_id), task)

    session = registry.get(device_id)
    if session is not None:
        sent = await dispatch_task_to_session(session, task)
        return DeviceTaskRouteResult(
            "sent" if sent else "queued",
            sent,
            pending_count(device_id),
            task,
        )

    queue_depth = enqueue_pending_task(device_id, task)
    await publish_task_available_safe(device_id, str(task.get("task_id", "")))
    return DeviceTaskRouteResult("queued", False, queue_depth, task)
