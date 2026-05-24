"""Device task projection helpers and store facade."""
from __future__ import annotations

from typing import Any

from .intent import resolve_voice_task
from .safety import DEFAULT_FEED, safe_point, validate_run_path_params
from . import store as store_mod
from .store import DeviceTaskStore, InMemoryDeviceTaskStore


def reset_tasks_for_tests() -> None:
    store_mod.task_store.reset()


def install_task_store_for_tests(store: DeviceTaskStore | None = None) -> DeviceTaskStore:
    selected = store or InMemoryDeviceTaskStore()
    store_mod.set_task_store_for_tests(selected)
    return selected


def _next_task_id() -> str:
    return store_mod.task_store.next_task_id()


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
    store_mod.task_store.create_task_state(task, status="created")
    return task


def create_task_from_transcript(device_id: str, text: str, request_id: str | None = None) -> dict[str, Any]:
    return project_to_motion_task(device_id, resolve_voice_task(text), request_id)


def record_motion_event(event: dict[str, Any]) -> dict[str, Any]:
    return store_mod.task_store.record_motion_event(event)


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


def ack_processing_task(device_id: str, task_id: str) -> bool:
    return store_mod.task_store.ack_processing(device_id, task_id)


def recover_stale_processing(device_id: str, timeout_sec: float = 120.0) -> int:
    return store_mod.task_store.recover_stale_processing(device_id, timeout_sec=timeout_sec)


def pending_count(device_id: str | None = None) -> int:
    return store_mod.task_store.pending_count(device_id)
