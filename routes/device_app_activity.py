"""LiMa native device app activity and timeline routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from device_gateway.tasks import task_snapshot
from device_ledger.projection import device_projection, task_projection
from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err

router = APIRouter(prefix="/device/v1/app", tags=["device-app-activity"])


@router.get("/tasks/{task_id}/timeline")
async def get_task_timeline(task_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account

    state = task_projection.rebuild_state(task_id)
    device_id = state.get("device_id", "")
    if not device_id:
        snapshot = task_snapshot(task_id)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("task"), dict):
            device_id = str(snapshot["task"].get("device_id", ""))
    if not device_id:
        return err(404, "task not found", 404)

    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied

    return {
        "state": state,
        "timeline": task_projection.timeline(task_id),
        "duration": task_projection.task_duration(task_id),
    }


@router.get("/devices/{device_id}/activity")
async def get_device_activity(
    device_id: str,
    authorization: str = Header(default=""),
    limit: int = Query(100, ge=1, le=1000),
):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    return device_projection.device_summary(device_id, limit=limit)
