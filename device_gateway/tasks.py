"""Device task projection helpers and store facade."""

from __future__ import annotations

from typing import Any

from device_artifacts.store import artifact_store
from device_ledger.events import new_event
from device_ledger.store import ledger_store

from .intent import resolve_voice_task
from .safety import DEFAULT_FEED, safe_point
from .path_validator import validate_capability_params
from .path_pipeline import render_svg_task, render_text_task
from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore

CONTROL_CAPABILITIES = frozenset({"home", "pause", "resume", "stop", "get_device_info"})
TERMINAL_PHASES = frozenset({"done", "failed", "cancelled"})


def reset_tasks_for_tests() -> None:
    store_mod.task_store.reset()
    ledger_store.reset()
    artifact_store.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


def _looks_like_svg_path(text: str) -> bool:
    """Heuristic: does the text look like an SVG path 'd' attribute?"""
    stripped = text.strip()
    if not stripped:
        return False
    first = stripped[0]
    return first in "MmLCcQqHhVvZz"


def project_to_motion_task(device_id: str, voice_task: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    capability = voice_task["capability"]
    params = voice_task.get("params", {})
    if capability == "write_text":
        rendered = render_text_task(str(params.get("text", "")))
        run_params = {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
            "preview_svg": rendered.get("preview_svg", ""),
        }
    elif capability == "draw_generated":
        prompt = str(params.get("prompt", ""))[:120]
        if _looks_like_svg_path(prompt):
            rendered = render_svg_task(prompt)
        else:
            rendered = render_text_task(prompt or "?")
        run_params = {
            "feed": DEFAULT_FEED,
            "path": rendered["path"],
            "source_capability": "draw_generated",
            "prompt": prompt,
            "preview_svg": rendered.get("preview_svg", ""),
        }
    elif capability in CONTROL_CAPABILITIES:
        run_params = {
            "source_capability": capability,
        }
    else:
        run_params = {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}

    sanitized, error = validate_capability_params(capability, run_params)
    if error:
        task_id = _next_task_id()
        task = {
            "type": "motion_task",
            "task_id": task_id,
            "device_id": device_id,
            "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
            "source": voice_task.get("source", "voice"),
            "params": {},
            "error": {"code": error, "reason": f"validation failed: {error}"},
        }
        if request_id:
            task["request_id"] = request_id
        store_mod.task_store.create_task_state(task, status="failed")
        _record_task_created(task, status="failed")
        return task

    task_id = _next_task_id()
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability if capability in CONTROL_CAPABILITIES else "run_path",
        "source": voice_task.get("source", "voice"),
        "params": sanitized,
    }
    if request_id:
        task["request_id"] = request_id
    store_mod.task_store.create_task_state(task, status="created")
    _record_task_created(task, status="created")
    _record_preview_artifact(task)
    return task


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return project_to_motion_task(device_id, resolve_voice_task(text), request_id)


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    summary = store_mod.task_store.record_motion_event(event)
    ledger_store.append_event(
        new_event(
            event_type="motion_event",
            task_id=str(event["task_id"]),
            device_id=str(event.get("device_id", "")),
            payload={"motion_event": event},
        )
    )
    if event.get("phase") in TERMINAL_PHASES:
        ledger_store.append_event(
            new_event(
                event_type="task_terminal",
                task_id=str(event["task_id"]),
                device_id=str(event.get("device_id", "")),
                payload={"terminal_event": event},
            )
        )
        artifact_store.put_artifact(
            task_id=str(event["task_id"]),
            artifact_type="terminal_result",
            content=event,
            retention_days=90,
        )
    return summary


def task_snapshot(task_id: str) -> dict[str, Any] | None:
    return store_mod.task_store.task_snapshot(task_id)


def enqueue_pending_task(device_id: str, task: dict[str, Any]) -> int:
    return store_mod.task_store.enqueue_pending_task(device_id, task)


def pop_pending_tasks(device_id: str, limit: int = 16) -> list[dict[str, Any]]:
    return store_mod.task_store.pop_pending_tasks(device_id, limit=limit)


def requeue_pending_tasks(device_id: str, tasks: list[dict[str, Any]]) -> int:
    return store_mod.task_store.requeue_pending_tasks(device_id, tasks)


def mark_task_dispatched(task_id: str) -> None:
    store_mod.task_store.mark_task_dispatched(task_id)
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


def _record_task_created(task: dict[str, Any], status: str) -> None:
    ledger_store.append_event(
        new_event(
            event_type="task_created",
            task_id=str(task["task_id"]),
            device_id=str(task.get("device_id", "")),
            payload={"task": task, "status": status},
        )
    )


def _record_preview_artifact(task: dict[str, Any]) -> None:
    params = task.get("params", {})
    if not isinstance(params, dict):
        return
    preview_svg = params.get("preview_svg")
    if not isinstance(preview_svg, str) or not preview_svg:
        return
    artifact_store.put_artifact(
        task_id=str(task["task_id"]),
        artifact_type="preview_svg",
        content=preview_svg,
        retention_days=30,
    )
