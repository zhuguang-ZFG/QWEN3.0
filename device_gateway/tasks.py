"""In-memory first-slice device task state and projection."""
from __future__ import annotations

import itertools
from typing import Any

from .intent import resolve_voice_task
from .safety import DEFAULT_FEED, safe_point, validate_run_path_params

_counter = itertools.count(1)
_tasks: dict[str, dict[str, Any]] = {}


def reset_tasks_for_tests() -> None:
    _tasks.clear()


def _next_task_id() -> str:
    return f"task-{next(_counter):06d}"


def _write_text_path(text: str) -> list[dict[str, float]]:
    width = max(10, min(70, 8 * max(1, len(text))))
    return [
        safe_point(10, 10, 0),
        safe_point(10 + width, 10, 0),
        safe_point(10 + width, 25, 0),
        safe_point(10, 25, 0),
        safe_point(10, 10, 0),
    ]


def _star_path() -> list[dict[str, float]]:
    return [
        safe_point(50, 10, 0),
        safe_point(60, 40, 0),
        safe_point(90, 40, 0),
        safe_point(65, 58, 0),
        safe_point(75, 88, 0),
        safe_point(50, 70, 0),
        safe_point(25, 88, 0),
        safe_point(35, 58, 0),
        safe_point(10, 40, 0),
        safe_point(40, 40, 0),
        safe_point(50, 10, 0),
    ]


def project_to_motion_task(device_id: str, voice_task: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    capability = voice_task["capability"]
    params = voice_task.get("params", {})
    if capability == "write_text":
        run_params = {
            "feed": DEFAULT_FEED,
            "path": _write_text_path(str(params.get("text", ""))),
            "source_capability": "write_text",
            "text": str(params.get("text", ""))[:80],
        }
    elif capability == "draw_generated":
        run_params = {
            "feed": DEFAULT_FEED,
            "path": _star_path(),
            "source_capability": "draw_generated",
            "prompt": str(params.get("prompt", ""))[:120],
        }
    else:
        run_params = {"feed": DEFAULT_FEED, "path": [safe_point(0, 0, 0)], "source_capability": capability}
    run_params = validate_run_path_params(run_params)
    task_id = _next_task_id()
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": "run_path",
        "source": voice_task.get("source", "voice"),
        "params": run_params,
    }
    if request_id:
        task["request_id"] = request_id
    _tasks[task_id] = {"task": task, "status": "queued", "events": []}
    return task


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return project_to_motion_task(device_id, resolve_voice_task(text), request_id)


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    task_id = event["task_id"]
    state = _tasks.setdefault(task_id, {"task": None, "status": "unknown", "events": []})
    state["status"] = event["phase"]
    state["events"].append(event)
    return {"task_id": task_id, "phase": event["phase"], "event_count": len(state["events"])}


def task_snapshot(task_id: str) -> dict[str, Any] | None:
    return _tasks.get(task_id)

