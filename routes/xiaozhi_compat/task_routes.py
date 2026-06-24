"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


import logging
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .shared import (
    authorize,
    ok,
    err,
    read_body,
    connect,
    require_device_access,
    str_field,
    build_gateway_task,
    json_params,
    now,
    task_payload,
    dispatch_or_enqueue,
    query_int,
    ALLOWED_TASKS,
    ALLOWED_SOURCES,
    ALLOWED_TASK_STATUSES,
)
from device_gateway.tasks import record_motion_event, task_snapshot
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError

_log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/devices/{device_id}/tasks")
async def submit_task(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """提交运动任务。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    intent = str_field(body, "capability", "intent")
    if intent not in ALLOWED_TASKS:
        return err(4001, "unsupported capability", 400)
    source = str_field(body, "source") or "api"
    if source not in ALLOWED_SOURCES:
        return err(400, "invalid source", 400)
    raw_params = body.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    member_id = str_field(body, "memberId", "member_id") or None
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        if member_id:
            member = conn.execute(
                "SELECT 1 FROM v2_member WHERE id=? AND device_id=? AND status='active'", (member_id, device_id)
            ).fetchone()
            if member is None:
                return err(404, "member not found", 404)
        task, error = build_gateway_task(device_id, intent, params, source, str_field(body, "requestId", "request_id"))
        if error:
            return error
        if task is None:
            return err(4003, "task build failed", 400)
        status = "pending" if task["workflow_state"] == TaskState.WAITING_APPROVAL.value else "approved"
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, member_id, intent, params, source, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task["task_id"], device_id, account["id"], member_id, intent, json_params(params), source, status),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task["task_id"],)).fetchone()
    dispatch = {"sent": False, "queueDepth": 0, "dispatchStatus": "waiting_approval"}
    if status == "approved":
        dispatch = await dispatch_or_enqueue(device_id, task)
    data = task_payload(row)
    data.update(dispatch)
    return ok(data)


@router.get("/devices/{device_id}/tasks")
async def list_tasks(
    device_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """List tasks for a bound device."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    status = str(request.query_params.get("status") or "").strip()
    if status and status not in ALLOWED_TASK_STATUSES:
        return err(400, "invalid task status", 400)
    limit = query_int(request.query_params.get("limit"), default=20, minimum=1, maximum=100)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        if status:
            rows = conn.execute(
                "SELECT * FROM v2_task WHERE device_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
                (device_id, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM v2_task WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
    return ok([task_payload(row) for row in rows])


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Return a task detail if the current account can access the device."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    return ok(task_payload(row))


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """审批任务并下发。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute("UPDATE v2_task SET status='approved' WHERE id=? AND status='pending'", (task_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
    snapshot = task_snapshot(task_id) or {}
    task = snapshot.get("task") if isinstance(snapshot.get("task"), dict) else None
    dispatch = {"sent": False, "queueDepth": 0, "dispatchStatus": "not_dispatched"}
    if task is not None:
        try:
            if workflow.get_state(task_id) == TaskState.WAITING_APPROVAL:
                workflow.advance(task_id, TaskState.READY_TO_DISPATCH)
                task["workflow_state"] = TaskState.READY_TO_DISPATCH.value
        except WorkflowTransitionError as exc:
            _log.warning("approve workflow transition skipped task=%s err=%s", task_id, exc)
        dispatch = await dispatch_or_enqueue(row["device_id"], task)
    data = task_payload(row)
    data.update(dispatch)
    return ok(data)


@router.post("/tasks/{task_id}/reject")
async def reject_task(task_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """拒绝任务。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    reason = str_field(body, "reason", "comment") or "rejected"
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute(
            "UPDATE v2_task SET status='rejected', error_msg=?, completed_at=? WHERE id=?", (reason, now(), task_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
    record_motion_event(
        {
            "type": "motion_event",
            "device_id": row["device_id"],
            "task_id": task_id,
            "phase": "rejected",
            "error": {"code": "E_REJECTED", "reason": reason},
        }
    )
    try:
        if workflow.get_state(task_id) == TaskState.WAITING_APPROVAL:
            workflow.advance(task_id, TaskState.TERMINAL)
    except WorkflowTransitionError as exc:
        _log.warning("reject workflow transition skipped task=%s err=%s", task_id, exc)
    return ok(task_payload(row))


@router.get("/devices/{device_id}/tasks/pending")
async def pending_tasks(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """列出待审批任务。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_task WHERE device_id=? AND status='pending' ORDER BY created_at DESC", (device_id,)
        ).fetchall()
    return ok([task_payload(row) for row in rows])
