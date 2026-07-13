"""Persistence helpers for LiMa native device app task routes."""

from __future__ import annotations

import logging
from typing import Any


from device_gateway.tasks import record_motion_event, task_snapshot
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError
from routes.device_app_task_payloads import require_device_owner
from device_logic.gateway import dispatch_or_enqueue
from device_logic.db import connect
from device_logic.http import err, json_params, now, str_field

_log = logging.getLogger(__name__)
DB_TASK_SOURCES = {"client": "api", "app": "api"}


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
                str(task.get("app_capability") or task.get("capability") or "unknown"),
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
        # Atomic claim: only one concurrent approve wins.
        cur = conn.execute(
            "UPDATE v2_task SET status='approved', error_msg=NULL WHERE id=? AND status='pending'",
            (task_id,),
        )
        if getattr(cur, "rowcount", 0) != 1:
            return err(409, "task is no longer pending", 409), None
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


def revert_task_to_pending(task_id: str) -> None:
    """Best-effort revert an approved task back to pending after dispatch failure."""
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE v2_task SET status='pending', error_msg=NULL WHERE id=? AND status='approved'",
                (task_id,),
            )
            if getattr(cur, "rowcount", 0) > 0:
                conn.commit()
                _log.warning("reverted task %s to pending after dispatch failure", task_id)
    except Exception as exc:
        _log.warning("revert_task_to_pending failed task=%s err=%s", task_id, exc)


def mark_task_failed(task_id: str, reason: str) -> None:
    """Best-effort mark an inserted task as failed after a dispatch failure/rejection."""
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE v2_task SET status='failed', error_msg=?, completed_at=? "
                "WHERE id=? AND status IN ('pending', 'approved')",
                (reason, now(), task_id),
            )
            if getattr(cur, "rowcount", 0) > 0:
                conn.commit()
                _log.warning("marked task %s failed after dispatch failure: %s", task_id, reason)
    except Exception as exc:
        _log.warning("mark_task_failed failed task=%s err=%s", task_id, exc)


def set_task_status(task_id: str, new_status: str) -> None:
    """Best-effort update the status of a pending task (e.g. pending -> approved)."""
    try:
        with connect() as conn:
            cur = conn.execute(
                "UPDATE v2_task SET status=? WHERE id=? AND status='pending'",
                (new_status, task_id),
            )
            if getattr(cur, "rowcount", 0) > 0:
                conn.commit()
    except Exception as exc:
        _log.warning("set_task_status failed task=%s err=%s", task_id, exc)


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
        cur = conn.execute(
            "UPDATE v2_task SET status='rejected', error_msg=?, completed_at=? WHERE id=? AND status='pending'",
            (reason, now(), task_id),
        )
        if getattr(cur, "rowcount", 0) != 1:
            return err(409, "task is no longer pending", 409)
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
