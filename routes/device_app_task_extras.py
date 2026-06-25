"""LiMa native device app task preview and batch operations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.access import require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id, read_body, str_field
from routes.device_app_task_store import insert_task_row
from routes.device_app_tasks import _build_app_gateway_task, _dispatch_or_wait

router = APIRouter(prefix="/device/v1/app", tags=["device-app-task-extras"])

_MAX_BATCH_TASKS = 20
_BATCH_SOURCE = "api"
_PREVIEW_SOURCE = "preview"


@router.post("/tasks/preview")
async def preview_task(request: Request, authorization: str = Header(default="")):
    """Preview the pattern a task would draw without dispatching it."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_id = str_field(body, "deviceId", "device_id")
    if not device_id:
        return err(400, "deviceId is required", 400)
    with connect() as conn:
        denied = require_device_control(conn, account, device_id)
        if denied:
            return denied
    capability = str_field(body, "capability") or "write_text"
    raw_params = body.get("params")
    params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
    task, error = await _build_app_gateway_task(
        device_id,
        capability,
        params,
        _PREVIEW_SOURCE,
        f"preview_{new_id()}",
    )
    if error:
        return error
    assert task is not None
    path = task.get("params", {}).get("path", []) if isinstance(task.get("params"), dict) else []
    return {
        "preview": task.get("preview", ""),
        "estimatedDuration": task.get("estimated_duration_ms", 0),
        "pathPoints": len(path) if isinstance(path, list) else 0,
    }


@router.post("/devices/{device_id}/batch-tasks")
async def create_batch_tasks(device_id: str, request: Request, authorization: str = Header(default="")):
    """Create up to 20 tasks in a single batch and enqueue them."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    with connect() as conn:
        denied = require_device_control(conn, account, device_id)
        if denied:
            return denied
    raw_tasks = body.get("tasks")
    if not isinstance(raw_tasks, list):
        return err(400, "tasks array is required", 400)
    if len(raw_tasks) > _MAX_BATCH_TASKS:
        return err(400, f"max {_MAX_BATCH_TASKS} tasks per batch", 400)
    results: list[dict[str, Any]] = []
    for item in raw_tasks:
        if not isinstance(item, dict):
            results.append({"status": "failed", "error": "task item must be an object"})
            continue
        capability = str_field(item, "capability") or "write_text"
        raw_params = item.get("params")
        params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
        task, error = await _build_app_gateway_task(device_id, capability, params, _BATCH_SOURCE, new_id())
        if error:
            results.append({"status": "failed", "error": _error_message(error)})
            continue
        assert task is not None
        _dispatch, status = await _dispatch_or_wait(device_id, task, _BATCH_SOURCE, params)
        insert_task_row(device_id, account, task, _BATCH_SOURCE, status, item, params)
        results.append({"taskId": task["task_id"], "status": status})
    return {"tasks": results, "count": len(results)}


def _error_message(error: JSONResponse) -> str:
    try:
        payload = error.body
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        import json

        data = json.loads(payload) if isinstance(payload, str) else payload
        if isinstance(data, dict):
            return str(data.get("message", "unknown error"))
    except Exception as exc:
        return f"task build failed: {exc}"
    return "task build failed"
