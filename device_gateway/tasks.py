"""Device task projection helpers and store facade (public API)."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Any

from device_ledger.store import ledger_store
from observability import prometheus_metrics

from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore
from .task_creation import (
    create_task_from_transcript,
    create_task_from_transcript_async,
    project_to_motion_task,
    project_to_motion_task_async,
)
from .task_events import TERMINAL_PHASES, execute_recovery, record_motion_event
from device_workflow.state import TaskState

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
    voice_task: dict[str, Any] | None = None  # 预解析 voice_task；存在时跳过 transcript NL 解析


@dataclass(frozen=True)
class DeviceTaskRouteResult:
    status: str
    sent: bool
    queue_depth: int
    task: dict[str, Any]


async def create_and_route_task(
    request: DeviceTaskRequest,
    *,
    enqueue: bool = True,
) -> DeviceTaskRouteResult:
    """Create a motion task and optionally enqueue it.

    After enqueue, M1 tries online WSS push. Offline → ``queued_no_delivery``;
    online but incomplete drain → ``queued``; success → ``sent``.

    Pass ``enqueue=False`` when the caller must persist the task row first
    (insert-before-dispatch) and will call ``enqueue_pending_task`` itself.
    """
    device_id = request.device_id.strip()
    text = request.text.strip()
    create_kwargs: dict[str, Any] = {"request_id": request.request_id or None}
    if request.source:
        create_kwargs["source"] = request.source
    if request.entrypoint:
        create_kwargs["entrypoint"] = request.entrypoint
    if request.voice_task:
        task = await project_to_motion_task_async(device_id, request.voice_task, request.request_id or None)
    else:
        task = await create_task_from_transcript_async(device_id, text, **create_kwargs)
    capability = str(task.get("capability", "unknown"))
    source = str(task.get("source", request.source or "unknown"))
    if not task.get("error"):
        prometheus_metrics.record_device_task_issued(capability, source)

    if task.get("error"):
        queue_depth = await asyncio.to_thread(pending_count, device_id)
        return DeviceTaskRouteResult("failed", False, queue_depth, task)

    # Align with structured app path: high-risk / approval-gated tasks stay pending.
    if task.get("workflow_state") == TaskState.WAITING_APPROVAL.value:
        queue_depth = await asyncio.to_thread(pending_count, device_id)
        return DeviceTaskRouteResult("waiting_approval", False, queue_depth, task)

    if not enqueue:
        queue_depth = await asyncio.to_thread(pending_count, device_id)
        return DeviceTaskRouteResult("created", False, queue_depth, task)

    return await _enqueue_and_try_deliver(device_id, task, capability)


async def _enqueue_and_try_deliver(
    device_id: str,
    task: dict[str, Any],
    capability: str,
) -> DeviceTaskRouteResult:
    """Enqueue then push to online device WS if present (M1)."""
    from device_gateway.delivery_status import try_deliver_and_classify

    queue_depth = await asyncio.to_thread(enqueue_pending_task, device_id, task)
    total_pending = await asyncio.to_thread(pending_count)
    prometheus_metrics.set_device_tasks_pending(total_pending)
    sent, status = await try_deliver_and_classify(device_id)
    if not sent:
        prometheus_metrics.record_device_task_dispatched(capability, status)
    return DeviceTaskRouteResult(status, sent, queue_depth, task)


def reset_tasks_for_tests() -> None:
    if "pytest" not in sys.modules:
        raise RuntimeError("reset_tasks_for_tests is only available during testing")
    from device_artifacts.store import artifact_store

    store_mod.task_store.reset()
    ledger_store.reset()
    artifact_store.reset()
    from device_workflow.orchestrator import workflow

    workflow.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    if "pytest" not in sys.modules:
        raise RuntimeError("install_task_store_for_tests is only available during testing")
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected
