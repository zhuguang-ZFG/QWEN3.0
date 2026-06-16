"""Helper functions for WebSocket lifecycle (reconnect, reattach, recovery)."""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.sessions import DeviceSession
from device_gateway.tasks import ack_processing_task
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError

_log = logging.getLogger(__name__)


def reattach_tasks(session: DeviceSession, tasks: list[dict[str, Any]]) -> None:
    seen = set(session.inflight_tasks)
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id or task_id in seen:
            continue
        session.mark_task_dispatched(task)
        seen.add(task_id)
        _record_device_reconnected(session.device_id, task_id)
        _recover_workflow(task_id)


def _record_device_reconnected(device_id: str, task_id: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=device_id,
            payload={
                "motion_event": {
                    "type": "motion_event",
                    "device_id": device_id,
                    "task_id": task_id,
                    "phase": "device_reconnected",
                }
            },
        )
    )


def _recover_workflow(task_id: str) -> None:
    try:
        current = workflow.get_state(task_id)
        if current == TaskState.DISPATCHED:
            workflow.advance(task_id, TaskState.RUNNING)
            current = TaskState.RUNNING
        if current == TaskState.RUNNING:
            workflow.advance(task_id, TaskState.RECOVERING)
            workflow.advance(task_id, TaskState.RUNNING)
    except WorkflowTransitionError as exc:
        _log.debug("workflow reconnect recovery skipped task=%s err=%s", task_id, exc)
