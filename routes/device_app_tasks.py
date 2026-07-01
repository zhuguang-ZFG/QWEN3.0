"""LiMa native device app task routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from device_gateway import store as store_mod
from device_gateway.coordinator import MultiDeviceCoordinator
from device_gateway.path_validator import validate_capability_params
from device_gateway.task_creation import project_to_motion_task_async
from device_gateway.task_events import record_task_paused, record_task_resumed
from device_gateway.tasks import DeviceTaskRequest, create_and_route_task, task_snapshot
from device_workflow.state import TaskState
from routes.device_app_task_store import (
    approve_task_row,
    dispatch_approved_task,
    insert_task_row,
    record_rejection,
    reject_task_row,
)
from device_logic.gateway import dispatch_or_enqueue
from device_logic.access import require_device_access, require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, read_body, str_field
from routes.device_app_task_payloads import (
    merge_task_lists,
    require_device_owner,
    snapshot_payload,
    task_row_payload,
)

router = APIRouter(prefix="/device/v1/app", tags=["device-app-tasks"])

APP_TASK_CAPABILITIES = frozenset(
    {
        "run_path",
        "write_text",
        "draw_generated",
        "draw_image",
        "handwriting",
        "home",
        "pause",
        "resume",
        "stop",
        "estop",
        "get_device_info",
    }
)
APP_TASK_SOURCES = frozenset({"api", "client", "voice", "scheduled"})


def _normalize_capability(capability: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    source_capability = capability
    capability = "draw_generated" if capability == "draw_image" else capability
    if capability not in APP_TASK_CAPABILITIES:
        return "", {}, f"unsupported capability: {source_capability}"
    task_params = dict(params)
    task_params.setdefault("source_capability", source_capability)
    if capability == "draw_generated" and "imageUrl" in task_params and "prompt" not in task_params:
        task_params["prompt"] = str(task_params["imageUrl"])
    return capability, task_params, None


async def _build_app_gateway_task(
    device_id: str, capability: str, params: dict[str, Any], source: str, request_id: str
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    capability, task_params, error = _normalize_capability(capability, params)
    if error:
        return None, err(4001, error, 400)
    sanitized, validation_error = validate_capability_params(capability, task_params)
    if validation_error:
        return None, err(4002, f"validation failed: {validation_error}", 400)
    task = await project_to_motion_task_async(
        device_id,
        {"capability": capability, "params": sanitized, "source": source, "entrypoint": "app_api"},
        request_id or None,
    )
    task_error = task.get("error")
    if isinstance(task_error, dict):
        reason = task_error.get("reason") or task_error.get("code") or "task build failed"
        return None, err(4003, str(reason), 400)
    task["app_capability"] = capability
    return task, None


async def _dispatch_or_wait(
    device_id: str, task: dict[str, Any], source: str, params: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    approval_required = source == "voice" and bool(params.get("requireApproval"))
    waiting = task.get("workflow_state") == TaskState.WAITING_APPROVAL.value or approval_required
    if waiting:
        return {"sent": False, "queueDepth": 0, "dispatchStatus": "waiting_approval"}, "pending"
    return await dispatch_or_enqueue(device_id, task), "approved"


@router.post("/devices/{device_id}/tasks")
async def create_task(device_id: str, request: Request, authorization: str = Header(default="")):
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
    text = str_field(body, "text", "prompt", "instruction")
    if text:
        result = await create_and_route_task(
            DeviceTaskRequest(
                device_id=device_id,
                text=text,
                request_id=str_field(body, "requestId", "request_id"),
                source="app",
                entrypoint="app_api",
            )
        )
        return {
            "taskId": result.task["task_id"],
            "status": result.status,
            "sent": result.sent,
            "queueDepth": result.queue_depth,
            "task": result.task,
        }
    return await _create_structured_task(device_id, account, body)


async def _create_structured_task(
    device_id: str, account: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any] | JSONResponse:
    source = str_field(body, "source") or "api"
    if source not in APP_TASK_SOURCES:
        return err(400, "invalid source", 400)
    raw_params = body.get("params")
    params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
    capability = str_field(body, "capability", "intent") or "write_text"
    task, error = await _build_app_gateway_task(
        device_id,
        capability,
        params,
        source,
        str_field(body, "requestId", "request_id"),
    )
    if error:
        return error
    assert task is not None
    if capability == "pause":
        record_task_paused(str(task["task_id"]), device_id)
    elif capability == "resume":
        record_task_resumed(str(task["task_id"]), device_id)
    dispatch, status = await _dispatch_or_wait(device_id, task, source, params)
    row = insert_task_row(device_id, account, task, source, status, body, params)
    data = task_row_payload(row)
    data.update(dispatch)
    data.update({"task": task, "taskId": task["task_id"]})
    return data


@router.get("/tasks")
async def list_tasks(
    device_id: str,
    authorization: str = Header(default=""),
    status: str = "",
    limit: int = Query(20, ge=1, le=100),
):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        where = "WHERE device_id=? AND status=?" if status else "WHERE device_id=?"
        args = (device_id, status, limit) if status else (device_id, limit)
        rows = conn.execute(f"SELECT * FROM v2_task {where} ORDER BY created_at DESC LIMIT ?", args).fetchall()
        db_tasks = [task_row_payload(row) for row in rows]
        store_tasks = [
            task
            for task in store_mod.task_store.list_tasks_for_device(device_id, status=status, limit=limit)
            if isinstance(task, dict)
        ]
    tasks = merge_task_lists(db_tasks, store_tasks, limit, task_snapshot)
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    snapshot = task_snapshot(task_id)
    if snapshot and isinstance(snapshot.get("task"), dict):
        task = snapshot["task"]
        with connect() as conn:
            denied = require_device_access(conn, account, str(task.get("device_id", "")))
            if denied:
                return denied
        return snapshot_payload(snapshot)
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    return task_row_payload(row)


@router.post("/devices/{device_id}/voice-tasks/pending")
async def pending_voice_tasks(device_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_owner(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_task WHERE device_id=? AND status='pending' ORDER BY created_at DESC", (device_id,)
        ).fetchall()
    return {"tasks": [task_row_payload(row) for row in rows], "count": len(rows)}


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    row_or_error, task = approve_task_row(task_id, account)
    if isinstance(row_or_error, JSONResponse):
        return row_or_error
    dispatch = await dispatch_approved_task(task_id, row_or_error["device_id"], task)
    data = task_row_payload(row_or_error)
    data.update(dispatch)
    data["reason"] = str_field(body, "reason", "comment") or "approved"
    return data


@router.post("/tasks/{task_id}/reject")
async def reject_task(task_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    reason = str_field(body, "reason", "comment") or "rejected"
    row_or_error = reject_task_row(task_id, account, reason)
    if isinstance(row_or_error, JSONResponse):
        return row_or_error
    record_rejection(task_id, row_or_error["device_id"], reason)
    data = task_row_payload(row_or_error)
    data["reason"] = reason
    return data


@router.post("/devices/batch-draw")
async def batch_draw(request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    device_ids = body.get("device_ids")
    svg = str_field(body, "svg")
    coordinator_id = str_field(body, "coordinator_id", "coordinatorId")
    if not isinstance(device_ids, list) or not device_ids or not svg or not coordinator_id:
        return err(400, "device_ids (non-empty list), svg and coordinator_id are required", 400)

    with connect() as conn:
        for device_id in device_ids:
            if not isinstance(device_id, str) or not device_id.strip():
                return err(400, "device_ids must be non-empty strings", 400)
            denied = require_device_control(conn, account, device_id.strip())
            if denied:
                return denied

    result = await MultiDeviceCoordinator().execute_coordinated(svg, [d.strip() for d in device_ids], coordinator_id)
    return result
