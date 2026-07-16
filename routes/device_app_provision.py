"""Device discovery routes and retired insecure pre-binding endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.auth import authorize
from device_logic.http import err, read_body, str_field

router = APIRouter(prefix="/device/v1/app", tags=["device-app-provision"])
_log = logging.getLogger(__name__)

_UDP_DISCOVERY_MESSAGE = b'{"cmd":"discover","proto":"lima-device-v1"}'
_UDP_SCAN_PORTS = (5000, 8080, 1883, 12345)
_UDP_SCAN_TIMEOUT = 2.0


def _parse_discovery_response(data: bytes, addr: tuple[str, int]) -> dict[str, Any]:
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
    """Best-effort UDP broadcast scan for local devices."""
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
    """Report client-discovered devices or run a best-effort server UDP scan."""
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


@router.post("/devices/provision")
async def create_provision(authorization: str = Header(default="")) -> JSONResponse:
    """Retired: the flow lacked device proof and allowed unbound-SN ownership claims."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return err(410, "provisioning flow retired; use activation-code binding", 410)


@router.post("/devices/provision/confirm")
async def confirm_provision() -> JSONResponse:
    """Retired with create_provision; bearer pair tokens were not device proof."""
    return err(410, "provisioning flow retired; use activation-code binding", 410)
