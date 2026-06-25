"""LiMa native device app discovery and pairing routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import socket
import time
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.crud import bind_device
from device_logic.db import connect
from device_logic.errors import DeviceLogicError
from device_logic.http import err, expires_at, new_id, now, read_body, str_field

router = APIRouter(prefix="/device/v1/app", tags=["device-app-discovery"])
_log = logging.getLogger(__name__)

_UDP_DISCOVERY_MESSAGE = b'{"cmd":"discover","proto":"lima-device-v1"}'
_UDP_SCAN_PORTS = (5000, 8080, 1883, 12345)
_UDP_SCAN_TIMEOUT = 2.0


def _parse_discovery_response(data: bytes, addr: tuple[str, int]) -> dict[str, Any]:
    """Parse a UDP discovery response into a normalized device record."""
    device: dict[str, Any] = {
        "ip": addr[0],
        "port": addr[1],
        "raw": data.decode("utf-8", errors="replace"),
    }
    try:
        payload = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return device
    if isinstance(payload, dict):
        device["deviceSn"] = payload.get("deviceSn") or payload.get("device_sn") or ""
        device["model"] = payload.get("model") or ""
        device["firmwareVer"] = payload.get("firmwareVer") or payload.get("firmware_ver") or ""
    return device


def _server_udp_scan(timeout: float = _UDP_SCAN_TIMEOUT) -> list[dict[str, Any]]:
    """Best-effort UDP broadcast scan for local devices.

    Runs in a worker thread so the event loop is not blocked.
    """
    devices: list[dict[str, Any]] = []
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        for port in _UDP_SCAN_PORTS:
            try:
                sock.sendto(_UDP_DISCOVERY_MESSAGE, ("255.255.255.255", port))
            except OSError as exc:
                _log.debug("UDP broadcast to port %s failed: %s", port, exc)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
                devices.append(_parse_discovery_response(data, addr))
            except socket.timeout:
                break
            except OSError as exc:
                _log.debug("UDP receive error: %s", exc)
    except OSError as exc:
        _log.warning("Server UDP scan failed: %s", exc)
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError as exc:
                _log.debug("Error closing UDP socket: %s", exc)
    return devices


def _normalize_client_device(item: Any) -> dict[str, Any] | None:
    """Normalize a client-reported device entry."""
    if not isinstance(item, dict):
        return None
    device_sn = str_field(item, "deviceSn", "device_sn")
    if not device_sn:
        return None
    return {
        "deviceSn": device_sn,
        "model": str_field(item, "model") or "",
        "firmwareVer": str_field(item, "firmwareVer", "firmware_ver") or "",
        "ip": str_field(item, "ip") or "",
    }


@router.post("/devices/discover")
async def discover_devices(request: Request, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body

    client_devices = body.get("devices")
    if isinstance(client_devices, list) and client_devices:
        devices = [_normalize_client_device(item) for item in client_devices]
        return {"devices": [d for d in devices if d is not None], "source": "client_report"}

    devices = await asyncio.to_thread(_server_udp_scan)
    return {"devices": devices, "source": "server_scan"}


@router.post("/devices/pair")
async def create_pair(request: Request, authorization: str = Header(default="")) -> Any:
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

    pair_id = new_id()
    pair_token = secrets.token_urlsafe(32)
    server_url = os.environ.get("LIMA_DEVICE_WS_URL", "wss://chat.donglicao.com/device/v1/ws")
    expires = expires_at(1800)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_pair_request
            (id, pair_token, device_sn, account_id, wifi_ssid, server_url, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (pair_id, pair_token, device_sn, account["id"], wifi_ssid, server_url, expires),
        )
        conn.commit()

    return {
        "pairId": pair_id,
        "pairToken": pair_token,
        "deviceSn": device_sn,
        "serverUrl": server_url,
        "protocol": "lima-device-v1",
        "expiresIn": 1800,
        "configPayload": {
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
            "server_url": server_url,
            "pair_token": pair_token,
            "device_sn": device_sn,
        },
    }


@router.post("/devices/pair/confirm")
async def confirm_pair(request: Request) -> Any:
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    token = str_field(body, "pairToken", "pair_token", "provisionToken")
    device_sn = str_field(body, "deviceSn", "device_sn")
    if not token:
        return err(400, "pairToken is required", 400)
    if not device_sn:
        return err(400, "deviceSn is required", 400)

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_pair_request WHERE pair_token=? AND status='pending'", (token,)).fetchone()
        if row is None:
            return err(404, "pair token not found", 404)
        if row["expires_at"] < now():
            conn.execute("UPDATE v2_pair_request SET status='expired' WHERE id=?", (row["id"],))
            conn.commit()
            return err(400, "pair token expired", 400)
        if row["device_sn"] != device_sn:
            return err(400, "deviceSn does not match pair token", 400)
        account_id = row["account_id"]
        pair_request_id = row["id"]

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

        conn.execute("UPDATE v2_pair_request SET status='completed' WHERE id=?", (pair_request_id,))
        conn.commit()

    return {"deviceSn": device_sn, "status": "bound", "accountId": account_id}
