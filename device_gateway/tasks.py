"""Device task projection helpers and store facade (public API)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from device_ledger.store import ledger_store

from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore
from .task_creation import (
    create_task_from_transcript,
    create_task_from_transcript_async,
    project_to_motion_task,
    project_to_motion_task_async,
)
from .task_events import TERMINAL_PHASES, execute_recovery, record_motion_event
from .task_lifecycle import (
    ack_processing_task,
    active_tasks_for_device,
    enqueue_pending_task,
    mark_task_dispatched,
    pending_count,
    pop_pending_tasks,
    recover_stale_processing,
    remove_pending_task,
    requeue_pending_tasks,
    task_snapshot,
)
from routes.device_gateway_dispatch import dispatch_task_to_session, publish_task_available_safe
from device_gateway.sessions import registry

# Backward-compatible monkeypatch surface (tests patch device_gateway.tasks.*)
from .task_creation import (
    apply_profile_constraints,
    policy_engine,
    resolve_device_route_policy,
    resolve_profile,
    validate_capability_params,
    validate_route_policy,
)

__all__ = [
    "DeviceTaskRequest",
    "DeviceTaskRouteResult",
    "TERMINAL_PHASES",
    "ack_processing_task",
    "active_tasks_for_device",
    "create_and_route_task",
    "create_task_from_transcript",
    "create_task_from_transcript_async",
    "enqueue_pending_task",
    "execute_recovery",
    "install_task_store_for_tests",
    "mark_task_dispatched",
    "pending_count",
    "pop_pending_tasks",
    "project_to_motion_task",
    "project_to_motion_task_async",
    "record_motion_event",
    "recover_stale_processing",
    "remove_pending_task",
    "requeue_pending_tasks",
    "reset_tasks_for_tests",
    "task_snapshot",
]


@dataclass(frozen=True)
class DeviceTaskRequest:
    device_id: str
    text: str
    request_id: str = ""
    source: str = ""
    entrypoint: str = ""


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
    create_kwargs: dict[str, Any] = {"request_id": request.request_id or None}
    if request.source:
        create_kwargs["source"] = request.source
    if request.entrypoint:
        create_kwargs["entrypoint"] = request.entrypoint
    task = await create_task_from_transcript_async(device_id, text, **create_kwargs)
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


def reset_tasks_for_tests() -> None:
    from device_artifacts.store import artifact_store

    store_mod.task_store.reset()
    ledger_store.reset()
    artifact_store.reset()
    from device_workflow.orchestrator import workflow

    workflow.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected
