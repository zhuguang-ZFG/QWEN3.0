"""Device motion events, recovery execution, and terminal memory extraction."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from device_intelligence.recovery import recovery_action, should_retry
from device_ledger.events import new_event
from device_ledger.store import ledger_store
from device_logic.http import now
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState

from . import store as store_mod
from .task_lifecycle import enqueue_pending_task
from .task_ledger_events import (  # noqa: F401 (re-exports for backward compat)
    record_device_connected,
    record_device_disconnected,
    record_task_acknowledged,
    record_task_paused,
    record_task_progress,
    record_task_resumed,
)
from .task_recorder import record_device_consumed_route_evidence, record_recovery_route_evidence

try:
    from device_logic.notifications import dispatch_notification_later
except ImportError as _notifications_import_err:
    logging.warning("device_logic.notifications not available: %s", _notifications_import_err)
    dispatch_notification_later = None  # type: ignore[assignment]

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
        device_id = str(event.get("device_id", ""))
        ledger_store.append_event(
            new_event(
                event_type="task_terminal",
                task_id=task_id,
                device_id=device_id,
                payload={"terminal_event": event},
            )
        )
        terminal_content = dict(event)
        if device_id:
            terminal_content.setdefault("device_id", device_id)
        artifact_store.put_artifact(
            task_id=task_id,
            artifact_type="terminal_result",
            content=terminal_content,
            retention_days=90,
        )
        record_device_consumed_route_evidence(task_id, event)
        _extract_memory_from_terminal(task_id, str(event.get("device_id", "")), event)
        _try_dispatch_terminal_notification(task_id, device_id, event)
    return summary


def _try_dispatch_terminal_notification(
    task_id: str,
    device_id: str,
    event: dict[str, Any],
) -> None:
    """Best-effort push notification for terminal task phases."""
    if not device_id or dispatch_notification_later is None:
        return
    phase = event.get("phase", "")
    if phase == "done":
        event_type = "task_completed"
    elif phase == "failed":
        event_type = "task_failed"
    else:
        return
    error = event.get("error", "") if isinstance(event.get("error"), str) else ""
    data = {
        "task_name": task_id[:8],
        "task_id": task_id,
        "error": error,
        "completed_at": now(),
    }
    try:
        dispatch_notification_later(device_id, event_type, data)
    except Exception as exc:
        _log.warning(
            "terminal notification dispatch failed for task=%s device=%s: %s",
            task_id,
            device_id,
            exc,
            exc_info=True,
        )


def process_motion_event_core(device_id: str, message: dict[str, Any]) -> dict[str, Any]:
    """Shared core motion_event processing for REST, WS, and MQTT channels.

    Calls record_motion_event for persistence, updates device shadow,
    acknowledges the task, and records observability metrics.
    Returns the summary dict. Channel-specific response sending is the caller's job.
    """
    from device_intelligence.shadow import shadow_store
    from .task_lifecycle import ack_processing_task, record_motion_event_observability

    summary = record_motion_event(message)
    shadow_store.update_motion_event(message)
    ack_processing_task(device_id, message["task_id"])
    record_motion_event_observability(message, device_id)
    return summary


def _recovery_for_event(event: dict[str, Any]) -> Any | None:
    error = event.get("error")
    if not error:
        return None
    if isinstance(error, str):
        return recovery_action(error)
    code = event.get("code", 0)
    return recovery_action(f"{error}:{code}")


def record_motion_event_side_effects(device_id: str, message: dict[str, Any]) -> None:
    """Emit ledger events derived from a device motion_event payload."""
    phase = message.get("phase", "")
    task_id = str(message.get("task_id", ""))
    if phase == "accepted":
        record_task_acknowledged(task_id, device_id)
    if phase == "running" or "progress" in message:
        progress_value = message.get("progress", 0)
        if isinstance(progress_value, (int, float)):
            record_task_progress(task_id, device_id, int(progress_value))


def _advance_workflow_on_event(task_id: str, phase: str) -> None:
    if not task_id:
        return
    state_map = {
        "accepted": TaskState.DISPATCHED,
        "running": TaskState.IN_PROGRESS,
        "done": TaskState.COMPLETED,
        "failed": TaskState.FAILED,
        "cancelled": TaskState.CANCELLED,
    }
    target = state_map.get(phase)
    if target is None:
        return
    try:
        workflow.advance(task_id, target)
    except Exception:
        _log.warning("workflow advance failed task=%s phase=%s", task_id, phase, exc_info=True)


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


def execute_recovery(task_id: str, device_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
    """Execute recovery action for a failed task. Returns recovery result or None."""
    phase = event.get("phase", "")
    error = event.get("error", "")
    if phase != "failed" or not error:
        if not error and event.get("error_code"):
            error = {"code": event["error_code"]}
        else:
            return None
    if isinstance(error, dict):
        error_code = error.get("code", "")
    else:
        error_code = str(error)
    snapshot = store_mod.task_store.task_snapshot(task_id)
    attempt = snapshot.get("retry_count", 0) if snapshot else 0
    task = snapshot.get("task") if snapshot else None
    action = recovery_action(error_code)
    can_retry = action.action == "retry" and should_retry(error_code, attempt)
    result: dict[str, Any] = {"task_id": task_id, "explanation_zh": action.explanation_zh}
    if can_retry:
        store_mod.task_store.reset_task_for_retry(task_id)
        if task:
            enqueue_pending_task(device_id, task)
        result["action"] = "retry"
        result["attempt"] = attempt + 1
        result["task"] = task
        record_recovery_route_evidence(task_id, device_id, result, task=task)
        return result
    # No retry allowed: fall back to the safe stop action.
    result["action"] = "stop" if action.action == "retry" else action.action
    result["attempt"] = 1
    record_recovery_route_evidence(task_id, device_id, result, task=task)
    return result
