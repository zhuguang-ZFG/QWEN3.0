"""Device task queue, dispatch, and snapshot helpers."""

from __future__ import annotations

import logging
from typing import Any

from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from . import store as store_mod

_log = logging.getLogger(__name__)


def task_snapshot(task_id: str) -> dict[str, Any] | None:
    return store_mod.task_store.task_snapshot(task_id)


def active_tasks_for_device(device_id: str) -> list[dict[str, Any]]:
    return store_mod.task_store.active_tasks_for_device(device_id)


def enqueue_pending_task(device_id: str, task: dict[str, Any]) -> int:
    return store_mod.task_store.enqueue_pending_task(device_id, task)


def remove_pending_task(device_id: str, task_id: str) -> bool:
    return store_mod.task_store.remove_pending_task(device_id, task_id)


def pop_pending_tasks(device_id: str, limit: int = 16) -> list[dict[str, Any]]:
    return store_mod.task_store.pop_pending_tasks(device_id, limit=limit)


def requeue_pending_tasks(device_id: str, tasks: list[dict[str, Any]]) -> int:
    return store_mod.task_store.requeue_pending_tasks(device_id, tasks)


def mark_task_dispatched(task_id: str) -> None:
    store_mod.task_store.mark_task_dispatched(task_id)
    try:
        current = workflow.get_state(task_id)
        if current == TaskState.READY_TO_DISPATCH:
            workflow.advance(task_id, TaskState.DISPATCHED)
    except Exception:
        _log.debug("workflow advance skipped for legacy/missing task_id=%s", task_id, exc_info=True)
    snapshot = store_mod.task_store.task_snapshot(task_id)
    task = snapshot.get("task") if snapshot else None
    device_id = str(task.get("device_id", "")) if isinstance(task, dict) else ""
    ledger_store.append_event(
        new_event(
            event_type="task_dispatched",
            task_id=task_id,
            device_id=device_id,
            payload={"task_id": task_id},
        )
    )


def ack_processing_task(device_id: str, task_id: str) -> bool:
    return store_mod.task_store.ack_processing(device_id, task_id)


def recover_stale_processing(device_id: str, timeout_sec: float = 120.0) -> int:
    return store_mod.task_store.recover_stale_processing(device_id, timeout_sec=timeout_sec)


def pending_count(device_id: str | None = None) -> int:
    return store_mod.task_store.pending_count(device_id)
