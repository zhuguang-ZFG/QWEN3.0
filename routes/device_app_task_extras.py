"""LiMa native device app task preview and batch operations."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from config import settings
from device_logic.access import require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, new_id, read_body, str_field
from routes.device_app_task_store import insert_task_row, mark_task_failed, set_task_status
from routes.device_app_task_create import _build_app_gateway_task, _dispatch_or_wait
from routes.rate_limit_helper import check_key_limit

router = APIRouter(prefix="/device/v1/app", tags=["device-app-task-extras"])

_log = logging.getLogger(__name__)

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
        str(account.get("id", "")),
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
    # Pre-check: each task in the batch consumes a quota slot.
    for _ in raw_tasks:
        limited = check_key_limit(f"device_app_task:{account['id']}", settings.DEVICE.dlc_task_per_min)
        if limited is not None:
            return limited
    results: list[dict[str, Any]] = []
    for item in raw_tasks:
        if not isinstance(item, dict):
            results.append({"status": "failed", "error": "task item must be an object"})
            continue
        capability = str_field(item, "capability") or "write_text"
        raw_params = item.get("params")
        params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
        task, error = await _build_app_gateway_task(
            device_id, capability, params, _BATCH_SOURCE, new_id(), str(account.get("id", ""))
        )
        if error:
            results.append({"status": "failed", "error": _error_message(error)})
            continue
        assert task is not None
        results.append(await _insert_then_dispatch(device_id, account, task, item, params))
    return {"tasks": results, "count": len(results)}


async def _insert_then_dispatch(
    device_id: str, account: dict[str, Any], task: dict[str, Any], item: dict[str, Any], params: dict[str, Any]
) -> dict[str, Any]:
    """Insert the task row first, then dispatch — no ghost task on DB failure."""
    task_id = str(task["task_id"])
    try:
        insert_task_row(device_id, account, task, _BATCH_SOURCE, "pending", item, params)
    except Exception as exc:
        _log.warning("insert_task_row failed task=%s err=%s", task_id, exc)
        return {"taskId": task_id, "status": "failed", "error": str(exc)}
    try:
        _dispatch, status = await _dispatch_or_wait(device_id, task, _BATCH_SOURCE, params)
    except Exception as exc:
        _log.warning("dispatch failed after insert task=%s err=%s", task_id, exc)
        mark_task_failed(task_id, "dispatch failed")
        return {"taskId": task_id, "status": "failed", "error": str(exc)}
    if status != "pending":
        set_task_status(task_id, status)
    return {"taskId": task_id, "status": status}


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
