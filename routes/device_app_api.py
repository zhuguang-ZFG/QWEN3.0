"""LiMa native device app management routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic import (
    DeviceLogicError,
    bind_device as logic_bind_device,
    check_activation_code,
    get_device_row,
    list_device_rows,
    manual_add_device as logic_manual_add_device,
    new_activation_code,
    unbind_device as logic_unbind_device,
    update_device_row,
)
from device_logic.activation import ACTIVATION_TTL_SECONDS
from device_logic.access import require_device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.device_sn import validate_device_sn
from device_logic.http import err, new_id, now, read_body, str_field
from device_logic.payloads import device_payload
from device_logic.rate_limit import RateLimiter

router = APIRouter(prefix="/device/v1/app", tags=["device-app"])

# L2 fix: rate-limit device registration to 5 calls per 60 s per account.
# Prevents activation-code flooding and unbounded SQLite row creation.
_register_limiter = RateLimiter(max_calls=5, window_seconds=60)


def _device_error(exc: DeviceLogicError) -> JSONResponse:
    return err(exc.code, exc.message, exc.http_status)


@router.post("/devices/register")
async def register_device(request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    # L2 fix: rate-limit per account — blocks flooding before reading the request body.
    if not _register_limiter.is_allowed(account["id"]):
        return err(429, "Too many registration requests — try again later", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    activation_code = new_activation_code(str_field(body, "macAddress", "mac_address"))
    return {"activationCode": activation_code, "code": activation_code, "expiresIn": ACTIVATION_TTL_SECONDS}


@router.post("/devices/bind")
async def bind_device(request: Request, authorization: str = Header(default="")):
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
    # Q2 fix: validate device_sn format BEFORE consuming the activation code.
    # N1 made check_activation_code() DELETE the code on success, so a bad SN would
    # silently burn the one-time code without binding any device.
    try:
        device_sn = validate_device_sn(device_sn)
    except DeviceLogicError as exc:
        return _device_error(exc)
    if not check_activation_code(activation_code):
        return err(4004, "Invalid activation code", 400)
    try:
        with connect() as conn:
            result = logic_bind_device(
                conn,
                account_id=account["id"],
                device_sn=device_sn,
                model=str_field(body, "model") or "esp32s3_xyz",
                firmware_ver=str_field(body, "firmwareVer", "firmware_ver") or "",
                hardware_ver=str_field(body, "hardwareVer", "hardware_ver") or "",
                metadata=body.get("metadata"),
                new_id=new_id,
            )
    except DeviceLogicError as exc:
        return _device_error(exc)
    device = result["device"]
    return {
        "bindingId": result["binding_id"],
        "deviceId": result["device_id"],
        "device": device_payload(device),
    }


@router.get("/devices")
async def list_devices(authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        rows = list_device_rows(conn, account_id=account["id"], role=account.get("role", ""))
    devices = [device_payload(row) for row in rows]
    return {"devices": devices, "count": len(devices)}


@router.get("/devices/{device_id}")
async def get_device(device_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        row = get_device_row(conn, device_id)
    if row is None:
        return err(404, "device not found", 404)
    return device_payload(row)


@router.put("/devices/{device_id}")
async def update_device(device_id: str, request: Request, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        try:
            row = update_device_row(conn, device_id=device_id, body=body)
        except DeviceLogicError as exc:
            return _device_error(exc)
    return device_payload(row)


@router.post("/devices/{device_id}/unbind")
async def unbind_device(device_id: str, authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        try:
            logic_unbind_device(
                conn,
                device_id=device_id,
                account_id=account["id"],
                role=account.get("role", ""),
                now=now,
            )
        except DeviceLogicError as exc:
            return _device_error(exc)
    return {"deviceId": device_id, "status": "unbound"}


@router.post("/devices/manual-add")
async def manual_add_device(request: Request, authorization: str = Header(default="")):
    """管理员手动添加设备（无需激活码）。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    if account.get("role") != "admin":
        return err(403, "only admin can manually add devices", 403)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_sn = str_field(body, "deviceSn", "device_sn")
    if not device_sn:
        return err(400, "deviceSn is required", 400)
    try:
        with connect() as conn:
            row = logic_manual_add_device(
                conn,
                device_sn=device_sn,
                model=str_field(body, "model") or "esp32s3_xyz",
                firmware_ver=str_field(body, "firmwareVer", "firmware_ver") or "",
                hardware_ver=str_field(body, "hardwareVer", "hardware_ver") or "",
                metadata=body.get("metadata"),
                new_id=new_id,
            )
    except DeviceLogicError as exc:
        return _device_error(exc)
    return {"device": device_payload(row)}
