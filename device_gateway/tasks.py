"""In-memory first-slice device task state and projection."""
from __future__ import annotations

from collections import deque
import itertools
import threading
from typing import Any

from .intent import resolve_voice_task
from .safety import DEFAULT_FEED, safe_point, validate_run_path_params

_counter = itertools.count(1)
_tasks: dict[str, dict[str, Any]] = {}
_pending_by_device: dict[str, deque[dict[str, Any]]] = {}
_lock = threading.RLock()


def reset_tasks_for_tests() -> None:
    global _counter
    with _lock:
        _counter = itertools.count(1)
        _tasks.clear()
        _pending_by_device.clear()


def _next_task_id() -> str:
    with _lock:
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
    with _lock:
        _tasks[task_id] = {"task": task, "status": "created", "events": []}
    return task


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return project_to_motion_task(device_id, resolve_voice_task(text), request_id)


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    task_id = event["task_id"]
    with _lock:
        state = _tasks.setdefault(task_id, {"task": None, "status": "unknown", "events": []})
        state["status"] = event["phase"]
        state["events"].append(event)
        return {"task_id": task_id, "phase": event["phase"], "event_count": len(state["events"])}


def task_snapshot(task_id: str) -> dict[str, Any] | None:
    with _lock:
        return _tasks.get(task_id)


def enqueue_pending_task(device_id: str, task: dict[str, Any]) -> int:
    with _lock:
        _pending_by_device.setdefault(device_id, deque()).append(task)
        state = _tasks.setdefault(task["task_id"], {"task": task, "status": "created", "events": []})
        state["task"] = task
        state["status"] = "queued"
        return len(_pending_by_device[device_id])


def pop_pending_tasks(device_id: str, limit: int = 16) -> list[dict[str, Any]]:
    with _lock:
        queue = _pending_by_device.get(device_id)
        if not queue:
            return []
        tasks: list[dict[str, Any]] = []
        while queue and len(tasks) < limit:
            task = queue.popleft()
            tasks.append(task)
            state = _tasks.setdefault(task["task_id"], {"task": task, "status": "queued", "events": []})
            state["status"] = "dispatching"
        if not queue:
            _pending_by_device.pop(device_id, None)
        return tasks


def mark_task_sent(task_id: str) -> None:
    with _lock:
        state = _tasks.get(task_id)
        if state:
            state["status"] = "sent"


def pending_count(device_id: str | None = None) -> int:
    with _lock:
        if device_id is not None:
            return len(_pending_by_device.get(device_id, ()))
        return sum(len(queue) for queue in _pending_by_device.values())
