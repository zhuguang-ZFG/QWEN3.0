"""Device motion events, recovery execution, and terminal memory extraction."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from device_intelligence.recovery import recovery_action, should_retry
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from . import store as store_mod
from .task_lifecycle import enqueue_pending_task

_log = logging.getLogger(__name__)

TERMINAL_PHASES = frozenset({"done", "failed", "cancelled"})


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    from device_artifacts.store import artifact_store

    summary = store_mod.task_store.record_motion_event(event)
    task_id = str(event.get("task_id", ""))
    phase = event.get("phase", "")
    payload: dict[str, Any] = {"motion_event": event}
    if phase == "failed":
        recovery = _recovery_for_event(event)
        if recovery is not None:
            payload["recovery"] = asdict(recovery)
    _advance_workflow_on_event(task_id, phase)
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=str(event.get("device_id", "")),
            payload=payload,
        )
    )
    if phase in TERMINAL_PHASES:
        ledger_store.append_event(
            new_event(
                event_type="task_terminal",
                task_id=task_id,
                device_id=str(event.get("device_id", "")),
                payload={"terminal_event": event},
            )
        )
        artifact_store.put_artifact(
            task_id=task_id,
            artifact_type="terminal_result",
            content=event,
            retention_days=90,
        )
        _extract_memory_from_terminal(task_id, str(event.get("device_id", "")), event)
    return summary


def _extract_memory_from_terminal(task_id: str, device_id: str, event: dict[str, Any]) -> None:
    """Best-effort memory extraction from terminal task events."""
    try:
        from device_memory.extractor import extract_device_failure_from_event, extract_episode_from_terminal
        from device_memory.quality_gates import should_learn_entry
        from device_ledger.events import new_event as _ledger_new_event
        from routes.device_memory import get_memory_store

        syn_event = _ledger_new_event(
            event_type="task_terminal",
            task_id=task_id,
            device_id=device_id,
            payload={"terminal_event": event},
        )
        episode = extract_episode_from_terminal(syn_event, device_id, task_id)
        if episode is not None and should_learn_entry(episode):
            get_memory_store().create(episode)
            _log.debug("memory episode stored device=%s task=%s phase=%s", device_id, task_id, event.get("phase", ""))

        failure_entry = extract_device_failure_from_event(syn_event, device_id)
        if failure_entry is not None and should_learn_entry(failure_entry):
            get_memory_store().create(failure_entry)
    except Exception:
        _log.warning(
            "memory extraction failed device=%s task=%s; skipping to avoid blocking task lifecycle",
            device_id,
            task_id,
            exc_info=True,
        )


def _recovery_for_event(event: dict[str, Any]) -> Any | None:
    error = event.get("error")
    code = ""
    if isinstance(error, dict):
        code = str(error.get("code", ""))
    code = code or str(event.get("error_code", ""))
    if not code:
        return None
    return recovery_action(code)


def _advance_workflow_on_event(task_id: str, phase: str) -> None:
    """Best-effort workflow advancement from motion events."""
    if not task_id:
        return
    try:
        current = workflow.get_state(task_id)
    except Exception:
        return
    if phase == "processing" and current == TaskState.DISPATCHED:
        workflow.advance(task_id, TaskState.RUNNING)
    elif phase in TERMINAL_PHASES and current in (TaskState.RUNNING, TaskState.RECOVERING):
        workflow.advance(task_id, TaskState.TERMINAL)


def execute_recovery(task_id: str, device_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
    """Convert recovery decision into actionable retry/home/stop commands."""
    phase = event.get("phase", "")
    if phase != "failed":
        return None

    recovery = _recovery_for_event(event)
    if recovery is None:
        return None

    attempt = store_mod.task_store.increment_retry_count(task_id)

    action = recovery.action
    result: dict[str, Any] = {
        "action": action,
        "attempt": attempt,
        "explanation_zh": recovery.explanation_zh,
    }

    if action == "retry":
        if should_retry(str(_recovery_code(event)), attempt - 1):
            task = _retry_task(task_id, device_id)
            result["task"] = task
        else:
            action = "stop"
            result["action"] = action
    elif action == "home":
        _issue_home_command(device_id, task_id)

    return result


def _recovery_code(event: dict[str, Any]) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        return str(error.get("code", ""))
    return str(event.get("error_code", ""))


def _retry_task(task_id: str, device_id: str) -> dict[str, Any]:
    """Re-dispatch a previously failed task by referencing its snapshot."""
    snap = store_mod.task_store.task_snapshot(task_id)
    if not snap:
        return {"task_id": task_id, "error": "snapshot_not_found"}

    task = snap.get("task") if isinstance(snap, dict) else snap
    if not isinstance(task, dict):
        return {"task_id": task_id, "error": "snapshot_invalid"}

    task["_retry_attempt"] = snap.get("retry_count", 0) if isinstance(snap, dict) else 0
    store_mod.task_store.reset_task_for_retry(task_id)
    enqueue_pending_task(device_id, task)
    return task


def _issue_home_command(device_id: str, task_id: str) -> None:
    """Record home command in ledger for operator or session to pick up."""
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=task_id,
            device_id=device_id,
            payload={
                "motion_event": {
                    "type": "control_command",
                    "device_id": device_id,
                    "task_id": task_id,
                    "command": "home",
                    "reason": "recovery_action_home",
                }
            },
        )
    )
