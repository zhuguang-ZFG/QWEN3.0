"""LiMa native device app task routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from device_gateway import store as store_mod
from device_gateway.coordinator import MultiDeviceCoordinator
from device_gateway.tasks import create_and_route_task, task_snapshot
from device_gateway.tasks import DeviceTaskRequest
from device_logic.access import require_device_access, require_device_control
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, read_body, str_field
from routes.device_app_task_create import _create_structured_task
from routes.device_app_task_payloads import (
    merge_task_lists,
    require_device_owner,
    snapshot_payload,
    task_row_payload,
)
from routes.device_app_task_store import (
    approve_task_row,
    dispatch_approved_task,
    insert_task_row,
    record_rejection,
    reject_task_row,
)

router = APIRouter(prefix="/device/v1/app", tags=["device-app-tasks"])


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
        db_status = "pending" if result.status == "waiting_approval" else "approved"
        # Persist so approve/list can find free-text tasks (same table as structured).
        if not result.task.get("error") and result.task.get("task_id"):
            insert_task_row(device_id, account, result.task, "app", db_status, body, {})
        return {
            "taskId": result.task["task_id"],
            "status": result.status,
            "sent": result.sent,
            "queueDepth": result.queue_depth,
            "task": result.task,
            "dispatchStatus": result.status,
        }
    return await _create_structured_task(device_id, account, body)


@router.get("/tasks")
async def list_tasks(
    authorization: str = Header(default=""),
    device_id: str | None = Query(default=None),
    deviceId: str | None = Query(default=None),
    status: str = "",
    limit: int = Query(20, ge=1, le=100),
):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    # Mini-program may send camelCase deviceId; accept either alias.
    resolved = (device_id or deviceId or "").strip()
    if not resolved:
        return err(400, "device_id is required", 400)
    device_id = resolved
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
