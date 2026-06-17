"""LiMa native device app management routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_gateway import store as store_mod
from device_gateway.task_service import DeviceTaskRequest, create_and_route_task
from device_gateway.tasks import task_snapshot
from routes.xiaozhi_compat.activation import check_activation_code, new_activation_code
from routes.xiaozhi_compat.shared import (
    authorize,
    connect,
    device_payload,
    err,
    json_params,
    new_id,
    now,
    read_body,
    require_device_access,
    str_field,
)

router = APIRouter(prefix="/device/v1/app", tags=["device-app"])


def _device_row_by_sn(conn, device_sn: str):
    return conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (device_sn,)).fetchone()


def _task_summary_payload(task: dict[str, object]) -> dict[str, object]:
    return {
        "taskId": str(task.get("task_id", "")),
        "deviceId": str(task.get("device_id", "")),
        "capability": str(task.get("capability", "")),
        "source": str(task.get("source", "")),
        "status": str(task.get("status", "unknown")),
    }


def _apply_device_updates(body: dict[str, object]) -> tuple[dict[str, object], JSONResponse | None]:
    updates: dict[str, object] = {}
    for body_name, column_name in (
        ("model", "model"),
        ("firmwareVer", "firmware_ver"),
        ("firmware_ver", "firmware_ver"),
        ("hardwareVer", "hardware_ver"),
        ("hardware_ver", "hardware_ver"),
    ):
        value = body.get(body_name)
        if isinstance(value, str) and value.strip():
            updates[column_name] = value.strip()
    if "metadata" in body:
        metadata = body["metadata"]
        if isinstance(metadata, dict):
            updates["metadata"] = json_params(metadata)
        elif isinstance(metadata, str):
            updates["metadata"] = metadata
        else:
            return {}, err(400, "metadata must be an object or string", 400)
    if not updates:
        return {}, err(400, "no supported device fields provided", 400)
    return updates, None


@router.post("/devices/register")
async def register_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    activation_code = new_activation_code(str_field(body, "macAddress", "mac_address"))
    return {"activationCode": activation_code, "code": activation_code, "expiresIn": 600}


@router.post("/devices/bind")
async def bind_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_sn = str_field(body, "deviceSn", "device_sn")
    activation_code = str_field(body, "activationCode", "activation_code")
    if not device_sn or not activation_code:
        return err(400, "deviceSn and activationCode are required", 400)
    if not check_activation_code(activation_code):
        return err(4004, "Invalid activation code", 400)
    with connect() as conn:
        owner = conn.execute(
            """
            SELECT account_id
            FROM v2_device_binding
            WHERE device_id=(SELECT id FROM v2_device WHERE device_sn=?)
              AND bind_mode='owner'
              AND status='active'
            """,
            (device_sn,),
        ).fetchone()
        if owner is not None and owner["account_id"] != account["id"]:
            return err(4005, "Device is already bound", 400)
        device = _device_row_by_sn(conn, device_sn)
        if device is None:
            device_id = new_id()
            conn.execute(
                "INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    device_sn,
                    str_field(body, "model") or "esp32s3_xyz",
                    str_field(body, "firmwareVer", "firmware_ver") or "",
                    str_field(body, "hardwareVer", "hardware_ver") or "",
                    json_params(body.get("metadata")) if isinstance(body.get("metadata"), dict) else body.get("metadata"),
                ),
            )
            device = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
        binding = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            (device["id"], account["id"]),
        ).fetchone()
        if binding is None:
            binding_id = new_id()
            conn.execute(
                "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')",
                (binding_id, device["id"], account["id"]),
            )
        else:
            binding_id = binding["id"]
            conn.execute("UPDATE v2_device_binding SET status='active', unbound_at=NULL WHERE id=?", (binding_id,))
        conn.commit()
    return {"bindingId": binding_id, "deviceId": device["id"], "device": device_payload(device)}


@router.get("/devices")
async def list_devices(authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        if account.get("role") == "admin":
            rows = conn.execute("SELECT * FROM v2_device ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.*
                FROM v2_device d
                JOIN v2_device_binding b ON b.device_id = d.id
                WHERE b.account_id=? AND b.status='active'
                ORDER BY b.bound_at DESC
                """,
                (account["id"],),
            ).fetchall()
    return {"devices": [device_payload(row) for row in rows], "count": len(rows)}


@router.get("/devices/{device_id}")
async def get_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        return err(404, "device not found", 404)
    return device_payload(row)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    updates, error = _apply_device_updates(body)
    if error:
        return error
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        assignments = ", ".join(f"{column}=?" for column in updates)
        result = conn.execute(
            f"UPDATE v2_device SET {assignments} WHERE id=?",
            (*updates.values(), device_id),
        )
        conn.commit()
        if result.rowcount < 1:
            return err(404, "device not found", 404)
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    return device_payload(row)


@router.post("/devices/{device_id}/unbind")
async def unbind_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        if account.get("role") == "admin":
            result = conn.execute(
                "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND status='active'",
                (now(), device_id),
            )
        else:
            result = conn.execute(
                "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND account_id=? AND status='active'",
                (now(), device_id, account["id"]),
            )
        conn.commit()
    if result.rowcount < 1:
        return err(404, "active binding not found", 404)
    return {"deviceId": device_id, "status": "unbound"}


@router.post("/devices/{device_id}/tasks")
async def create_task(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    text = str_field(body, "text", "prompt", "instruction")
    request_id = str_field(body, "requestId", "request_id")
    if not text:
        return err(400, "text is required", 400)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    result = await create_and_route_task(DeviceTaskRequest(device_id=device_id, text=text, request_id=request_id or ""))
    return {
        "status": result.status,
        "sent": result.sent,
        "queueDepth": result.queue_depth,
        "task": result.task,
    }


@router.get("/tasks")
async def list_tasks(device_id: str, authorization: str = Header(default=""), status: str = "", limit: int = 20) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    tasks = store_mod.task_store.list_tasks_for_device(device_id, status=status, limit=limit)
    return {"tasks": [_task_summary_payload(task) for task in tasks], "count": len(tasks)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    snapshot = task_snapshot(task_id)
    if not snapshot or not isinstance(snapshot.get("task"), dict):
        return err(404, "task not found", 404)
    task = snapshot["task"]
    with connect() as conn:
        denied = require_device_access(conn, account, str(task.get("device_id", "")))
        if denied:
            return denied
    return {
        "taskId": task_id,
        "deviceId": task.get("device_id", ""),
        "capability": task.get("capability", ""),
        "source": task.get("source", ""),
        "params": task.get("params", {}),
        "status": snapshot.get("status", "unknown"),
        "retryCount": snapshot.get("retry_count", 0),
        "events": snapshot.get("events", []),
    }
