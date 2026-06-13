"""Device management routes for XiaoZhi v1 compatibility API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .activation import ACTIVATION_TTL_SECONDS, check_activation_code, new_activation_code
from .shared import (
    authorize, ok, err, read_body, connect, now, new_id,
    str_field, json_params, device_payload, require_device_access
)

router = APIRouter()


@router.post("/devices/register")
async def register_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Generate a short-lived Phase 0 activation code for device pairing."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    activation_code = new_activation_code(str_field(body, "macAddress", "mac_address"))
    return ok({"activationCode": activation_code, "code": activation_code, "expiresIn": ACTIVATION_TTL_SECONDS})


@router.post("/devices/bind")
async def bind_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """设备绑定：deviceSn + activationCode。"""
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
            "SELECT account_id FROM v2_device_binding WHERE device_id=(SELECT id FROM v2_device WHERE device_sn=?) AND bind_mode='owner' AND status='active'",
            (device_sn,),
        ).fetchone()
        if owner is not None and owner["account_id"] != account["id"]:
            return err(4005, "Device is already bound", 400)
        device = conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (device_sn,)).fetchone()
        if device is None:
            device_id = new_id()
            conn.execute(
                "INSERT INTO v2_device (id, device_sn, model, metadata) VALUES (?, ?, ?, ?)",
                (device_id, device_sn, str_field(body, "model") or "esp32s3_xyz", json_params(body.get("metadata"))),
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
    return ok({"bindingId": binding_id, "deviceId": device["id"], "device": device_payload(device)})


@router.get("/devices")
async def list_devices(authorization: str = Header(default="")) -> JSONResponse:
    """List devices actively bound to the current account."""
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
    return ok([device_payload(row) for row in rows])


@router.get("/devices/{device_id}")
async def get_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Return a bound device detail."""
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
    return ok(device_payload(row))


@router.put("/devices/{device_id}")
async def update_device(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Update mutable device profile fields."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    updates: dict[str, Any] = {}
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
        if isinstance(body["metadata"], dict):
            updates["metadata"] = json_params(body["metadata"])
        elif isinstance(body["metadata"], str):
            updates["metadata"] = body["metadata"]
        else:
            return err(400, "metadata must be an object or string", 400)
    if not updates:
        return err(400, "no supported device fields provided", 400)
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
    return ok(device_payload(row))


@router.post("/devices/{device_id}/unbind")
async def unbind_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Mark the current account's active device binding as unbound."""
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
    return ok({"deviceId": device_id, "status": "unbound"})
