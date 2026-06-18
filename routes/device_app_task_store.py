"""Persistence helpers for LiMa native device app task routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi.responses import JSONResponse

from device_gateway.tasks import record_motion_event, task_snapshot
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError
from routes.device_app_task_payloads import require_device_owner
from routes.xiaozhi_compat.gateway import dispatch_or_enqueue
from routes.xiaozhi_compat.shared import connect, err, json_params, now, str_field

_log = logging.getLogger(__name__)
DB_TASK_SOURCES = {"client": "api"}


def insert_task_row(
    device_id: str,
    account: dict[str, Any],
    task: dict[str, Any],
    source: str,
    status: str,
    body: dict[str, Any],
    params: dict[str, Any],
):
    db_params = dict(task.get("params", {}))
    request_id = str_field(body, "requestId", "request_id")
    if request_id:
        db_params["requestId"] = request_id
    if isinstance(params.get("constraints"), dict):
        db_params["constraints"] = dict(params["constraints"])
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, intent, params, source, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                task["task_id"],
                device_id,
                account["id"],
                str(task.get("app_capability") or task["capability"]),
                json_params(db_params),
                DB_TASK_SOURCES.get(source, source),
                status,
            ),
        )
        conn.commit()
        return conn.execute("SELECT * FROM v2_task WHERE id=?", (task["task_id"],)).fetchone()


def approve_task_row(task_id: str, account: dict[str, Any]):
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404), None
        denied = require_device_owner(conn, account, row["device_id"])
        if denied:
            return denied, None
        if row["status"] != "pending":
            return err(400, "task is not pending", 400), None
        snapshot = task_snapshot(task_id)
        task = snapshot.get("task") if snapshot and isinstance(snapshot.get("task"), dict) else None
        if not isinstance(task, dict):
            return err(409, "task dispatch payload is unavailable", 409), None
        conn.execute("UPDATE v2_task SET status='approved', error_msg=NULL WHERE id=?", (task_id,))
        conn.commit()
        return conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone(), task


async def dispatch_approved_task(task_id: str, device_id: str, task: dict[str, Any] | None) -> dict[str, Any]:
    if task is None:
        return {"sent": False, "queueDepth": 0, "dispatchStatus": "not_dispatched"}
    try:
        if workflow.get_state(task_id) == TaskState.WAITING_APPROVAL:
            workflow.advance(task_id, TaskState.READY_TO_DISPATCH)
            task["workflow_state"] = TaskState.READY_TO_DISPATCH.value
    except WorkflowTransitionError as exc:
        _log.warning("approve workflow transition skipped task=%s err=%s", task_id, exc)
    return await dispatch_or_enqueue(device_id, task)


def reject_task_row(task_id: str, account: dict[str, Any], reason: str):
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return err(404, "task not found", 404)
        denied = require_device_owner(conn, account, row["device_id"])
        if denied:
            return denied
        if row["status"] != "pending":
            return err(400, "task is not pending", 400)
        conn.execute(
            "UPDATE v2_task SET status='rejected', error_msg=?, completed_at=? WHERE id=?",
            (reason, now(), task_id),
        )
        conn.commit()
        return conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()


def record_rejection(task_id: str, device_id: str, reason: str) -> None:
    record_motion_event(
        {
            "type": "motion_event",
            "device_id": device_id,
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
