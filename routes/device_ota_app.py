"""App-facing OTA endpoints for the device mobile app."""

from __future__ import annotations

import asyncio
import os
import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from device_gateway.sessions import registry
from device_ota.runtime import get_canary, get_gradual
from device_logic import get_device_row
from device_logic.access import device_access
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, read_body

router = APIRouter(prefix="/device/v1/ota", tags=["device-ota-app"])


def _device_connection_config() -> dict:
    """固件 OTA 响应所需的连接配置：WebSocket 段 + 服务器时间。

    关键：必须返回 websocket 段（非 null 对象），否则固件 application.cc:488-494
    会因 HasWebsocketConfig()=false 兜底走 MQTT，连不上 LiMa 的 WS 网关。
    mqtt 段不返回（缺失即 HasMqttConfig()=false，配合 websocket 段让固件正确走 WS）。
    """
    ws_url = os.environ.get("LIMA_DEVICE_WS_URL", "wss://chat.donglicao.com/device/v1/ws")
    return {
        "websocket": {"url": ws_url},
        "server_time": {
            "timestamp": int(time.time() * 1000),  # 毫秒（固件 ota.cc:292 按毫秒处理）
            "timezone_offset": 480,  # 中国 UTC+8，单位分钟（ota.cc:296 乘 60*1000）
        },
    }


def _current_firmware_version(device_id: str) -> str:
    session = registry.get(device_id)
    if session is not None:
        return str(session.fw_rev or "").strip() or "0.0.0"
    with connect() as conn:
        row = get_device_row(conn, device_id)
    return str(row["firmware_ver"] if row else "").strip() or "0.0.0"


def _ota_status_for_device(device_id: str, current_version: str) -> dict:
    """Build the app-facing OTA status for a single device."""
    canary = get_canary()
    gradual = get_gradual()
    available_version = canary.deployed_version or gradual.version or ""
    firmware = canary.firmware or gradual.firmware or {}
    selected = canary.is_canary(device_id) or gradual.is_device_selected(device_id)
    if not available_version or not firmware:
        return _status_payload(device_id, current_version, None, None, "", "no_release", False, False)
    if current_version == available_version:
        status = "up_to_date"
    elif selected:
        status = "available_selected"
    else:
        status = "available_not_selected"
    # 仅向真正被选中且待升级的设备下发 firmware payload（避免泄漏预发布工件位置/签名）。
    fw = firmware if (selected and status == "available_selected") else None
    return _status_payload(
        device_id,
        current_version,
        available_version,
        fw,
        firmware.get("release_notes", ""),
        status,
        selected,
        selected and status != "up_to_date",
    )


def _status_payload(
    device_id: str,
    current_version: str,
    available_version: str | None,
    firmware: dict | None,
    release_notes: str,
    status: str,
    selected: bool,
    rollback_available: bool,
) -> dict:
    """统一构造 OTA 状态响应，并合并固件连接配置（websocket/server_time）。"""
    return {
        "device_id": device_id,
        "current_version": current_version,
        "available_version": available_version,
        "firmware": firmware,
        "release_notes": release_notes,
        "status": status,
        "selected": selected,
        "rollback_available": rollback_available,
        **_device_connection_config(),
    }


def _verify_device_access(account: dict, device_id: str) -> JSONResponse | None:
    """Synchronous access check; returns an error response or None when allowed."""
    with connect() as conn:
        if not device_access(conn, account, device_id):
            return err(403, "Device is not bound to this account", 403)
    return None


def _resolve_account_for_device_check(authorization: str, device_sn_header: str, device_id: str) -> dict | JSONResponse:
    """Resolve the account for an OTA /check request.

    Primary: JWT bearer (app/小程序 走的标准鉴权).
    Fallback: 固件直连场景——固件无 JWT，发 Serial-Number（= device_sn）header。
    按 device_sn 查设备，若设备存在且已绑定 owner，则放行（OTA check 是只读，
    固件需拿到连接配置才能建立语音链路）。
    """
    account = authorize(authorization)
    if not isinstance(account, JSONResponse):
        return account
    # 固件直连兜底：用 Serial-Number（device_sn）查设备绑定
    sn = (device_sn_header or "").strip()
    if not sn:
        return err(401, "authentication required (authorization or Serial-Number)", 401)
    with connect() as conn:
        device = conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (sn,)).fetchone()
        if device is None:
            return err(404, "device not registered", 404)
        binding = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND bind_mode='owner' AND status='active'",
            (device["id"],),
        ).fetchone()
    if binding is None:
        return err(403, "device not bound to any account", 403)
    # 固件兜底不返回真实 account dict（无 JWT），返回最小占位让流程继续
    return {"id": binding["account_id"], "_via_device_sn": True}


@router.api_route("/check", methods=["GET", "POST"])
def app_check_ota(
    device_id: str,
    authorization: str = Header(default=""),
    serial_number: str = Header(default="", alias="Serial-Number"),
):
    """App/firmware-facing OTA check: current version, available version, selection status.

    Supports both GET (app/小程序) and POST (固件 ota.cc:189 发 POST 带 system_info body).
    Auth: JWT bearer 优先；固件直连时用 Serial-Number header（device_sn）兜底。

    Sync def: no await needed, so FastAPI dispatches on the threadpool and the
    short SQLite call does not block the event loop.
    """
    account = _resolve_account_for_device_check(authorization, serial_number, device_id)
    if isinstance(account, JSONResponse):
        return account
    device_id = device_id.strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    # 仅 app/小程序（JWT）路径校验账号-设备绑定；固件兜底已在 _resolve 内校验设备绑定
    if not account.get("_via_device_sn"):
        denied = _verify_device_access(account, device_id)
        if denied is not None:
            return denied
    current_version = _current_firmware_version(device_id)
    return JSONResponse(_ota_status_for_device(device_id, current_version))


@router.post("/start")
async def app_start_ota(request: Request, authorization: str = Header(default="")):
    """App-facing OTA start/rollback: add or remove the device from the canary rollout."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_id = str(body.get("device_id") or "").strip()
    rollback = bool(body.get("rollback"))
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    # Offload the blocking SQLite access check to a worker thread so the
    # event loop stays responsive during concurrent app requests.
    denied = await asyncio.to_thread(_verify_device_access, account, device_id)
    if denied is not None:
        return denied

    canary = get_canary()
    current_version = await asyncio.to_thread(_current_firmware_version, device_id)
    status = _ota_status_for_device(device_id, current_version)

    if rollback:
        if canary.is_canary(device_id):
            canary.remove_canary_device(device_id)
        status = _ota_status_for_device(device_id, current_version)
        return JSONResponse({"ok": True, **status})

    if status["status"] == "up_to_date":
        return JSONResponse({"ok": True, **status})

    if not canary.deployed_version:
        return err(400, "No active firmware release", 400)

    if not canary.is_canary(device_id):
        canary.add_canary_device(device_id)
    status = _ota_status_for_device(device_id, current_version)
    return JSONResponse({"ok": True, **status})
