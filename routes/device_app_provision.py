"""LiMa native device app provision routes（从 device_app_misc 拆出以控制行数）。"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.crud import bind_device
from device_logic.db import connect
from device_logic.errors import DeviceLogicError
from device_logic.http import err, expires_at, new_id, now, read_body, str_field

router = APIRouter(prefix="/device/v1/app", tags=["device-app-provision"])


def _build_provision_response(
    provision_id: str,
    provision_token: str,
    device_sn: str,
    server_url: str,
    wifi_ssid: str,
    wifi_password: str,
) -> dict:
    """组装配网响应体。"""
    return {
        "provisionId": provision_id,
        "provisionToken": provision_token,
        "deviceSn": device_sn,
        "serverUrl": server_url,
        "protocol": "lima-device-v1",
        "expiresIn": 1800,
        "configPayload": {
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
            "server_url": server_url,
            "pair_token": provision_token,
            "device_sn": device_sn,
        },
    }


def _validate_provision_token(conn, token: str, device_sn: str):
    """查找并校验配网 token；返回行或 JSONResponse 错误。"""
    row = conn.execute("SELECT * FROM v2_pair_request WHERE pair_token=? AND status='pending'", (token,)).fetchone()
    if row is None:
        return err(404, "provision token not found", 404)
    if row["expires_at"] < now():
        conn.execute("UPDATE v2_pair_request SET status='expired' WHERE id=?", (row["id"],))
        conn.commit()
        return err(400, "provision token expired", 400)
    if row["device_sn"] != device_sn:
        return err(400, "deviceSn does not match provision token", 400)
    return row


def _complete_provision_binding(conn, row, device_sn: str):
    """绑定设备并标记配网完成；返回 account_id 或 JSONResponse 错误。"""
    account_id = row["account_id"]
    try:
        bind_device(
            conn,
            account_id=account_id,
            device_sn=device_sn,
            model="esp32s3_xyz",
            firmware_ver="",
            hardware_ver="",
            metadata=None,
            new_id=new_id,
        )
    except DeviceLogicError as exc:
        return err(exc.code, exc.message, exc.http_status)
    conn.execute("UPDATE v2_pair_request SET status='completed' WHERE id=?", (row["id"],))
    conn.commit()
    return account_id


@router.post("/devices/provision")
async def create_provision(request: Request, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_sn = str_field(body, "deviceSn", "device_sn")
    wifi_ssid = str_field(body, "wifiSsid", "ssid")
    wifi_password = str_field(body, "wifiPassword", "password") or ""
    if not device_sn:
        return err(400, "deviceSn is required", 400)
    if not wifi_ssid:
        return err(400, "wifiSsid is required", 400)

    provision_id = new_id()
    provision_token = secrets.token_urlsafe(32)
    server_url = f"wss://{request.headers.get('host') or 'chat.donglicao.com'}/device/v1/ws"
    expires = expires_at(1800)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_pair_request
            (id, pair_token, device_sn, account_id, wifi_ssid, server_url, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (provision_id, provision_token, device_sn, account["id"], wifi_ssid, server_url, expires),
        )
        conn.commit()

    return _build_provision_response(
        provision_id, provision_token, device_sn, server_url, wifi_ssid, wifi_password
    )


@router.post("/devices/provision/confirm")
async def confirm_provision(request: Request) -> Any:
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    token = str_field(body, "provisionToken", "pair_token")
    device_sn = str_field(body, "deviceSn", "device_sn")
    if not token:
        return err(400, "provisionToken is required", 400)
    if not device_sn:
        return err(400, "deviceSn is required", 400)

    with connect() as conn:
        row = _validate_provision_token(conn, token, device_sn)
        if isinstance(row, JSONResponse):
            return row
        account_id = _complete_provision_binding(conn, row, device_sn)
        if isinstance(account_id, JSONResponse):
            return account_id

    return {"deviceSn": device_sn, "status": "bound", "accountId": account_id}
