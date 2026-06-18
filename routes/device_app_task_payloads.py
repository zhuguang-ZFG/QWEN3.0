"""Payload helpers for LiMa native device app task routes."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from routes.xiaozhi_compat.shared import err, is_owner, json_params, loads_json


def task_row_payload(row) -> dict[str, Any]:
    params = loads_json(row["params"])
    request_id = str(params.get("requestId") or params.get("request_id") or "")
    constraints = params.get("constraints") if isinstance(params.get("constraints"), dict) else {}
    return {
        "taskId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "capability": row["intent"],
        "params": params,
        "paramsJson": json_params(params),
        "requestId": request_id,
        "constraintsJson": json_params(constraints),
        "source": row["source"],
        "status": row["status"],
        "progress": row["progress"],
        "errorMsg": row["error_msg"],
        "memberId": row["member_id"],
        "createdAt": row["created_at"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
    }


def task_summary_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskId": str(task.get("task_id", "")),
        "deviceId": str(task.get("device_id", "")),
        "capability": str(task.get("capability", "")),
        "requestId": str(task.get("request_id", "")),
        "source": str(task.get("source", "")),
        "status": str(task.get("status", "unknown")),
    }


def snapshot_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    task = snapshot.get("task")
    task_data = task if isinstance(task, dict) else {}
    params = task_data.get("params", {}) if isinstance(task_data.get("params"), dict) else {}
    constraints = task_data.get("constraints", {}) if isinstance(task_data.get("constraints"), dict) else {}
    return {
        "taskId": str(task_data.get("task_id", "")),
        "id": str(task_data.get("task_id", "")),
        "deviceId": str(task_data.get("device_id", "")),
        "capability": str(task_data.get("capability", "")),
        "requestId": str(task_data.get("request_id", "")),
        "params": params,
        "paramsJson": json_params(params),
        "constraintsJson": json_params(constraints),
        "source": str(task_data.get("source", "")),
        "status": str(snapshot.get("status", "unknown")),
        "retryCount": snapshot.get("retry_count", 0),
        "events": snapshot.get("events", []),
    }


def merge_task_lists(
    db_tasks: list[dict[str, Any]],
    store_tasks: list[dict[str, Any]],
    limit: int,
    snapshot_fn,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {str(task["taskId"]): task for task in db_tasks}
    for task in store_tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id or task_id in merged:
            continue
        snapshot = snapshot_fn(task_id)
        merged[task_id] = snapshot_payload(snapshot) if snapshot else task_summary_payload(task)
    return list(merged.values())[:limit]


def require_device_owner(conn, account: dict[str, Any], device_id: str) -> JSONResponse | None:
    if not is_owner(conn, account, device_id):
        return err(403, "Device is not bound to this account", 403)
    return None
