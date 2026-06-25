"""App-facing OTA endpoints for the device mobile app."""

from __future__ import annotations

import asyncio

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

    canary_version = canary.deployed_version
    canary_firmware = canary.firmware
    gradual_version = gradual.version
    gradual_firmware = gradual.firmware

    selected_in_canary = canary.is_canary(device_id)
    # ponytail: is_device_selected recomputes O(N log N) sort + N SHA256 per
    # request. Ceiling: device pool ~10^4. Upgrade path: cache the current
    # stage's selected set in GradualRollout, recomputed on start/promote/rollback.
    selected_in_gradual = gradual.is_device_selected(device_id)

    available_version = canary_version or gradual_version or ""
    firmware = canary_firmware or gradual_firmware or {}
    selected = selected_in_canary or selected_in_gradual

    if not available_version or not firmware:
        return {
            "device_id": device_id,
            "current_version": current_version,
            "available_version": None,
            "firmware": None,
            "release_notes": "",
            "status": "no_release",
            "selected": False,
            "rollback_available": False,
        }

    if current_version == available_version:
        status = "up_to_date"
    elif selected:
        status = "available_selected"
    else:
        status = "available_not_selected"

    # Only hand the firmware payload (url/sha256/signature) to devices that are
    # actually selected for this release AND have an upgrade waiting. Returning
    # it to unselected devices would leak pre-release artifact locations and
    # signatures from ongoing canary/gradual rollouts.
    return {
        "device_id": device_id,
        "current_version": current_version,
        "available_version": available_version,
        "firmware": firmware if (selected and status == "available_selected") else None,
        "release_notes": firmware.get("release_notes", ""),
        "status": status,
        "selected": selected,
        "rollback_available": selected and status != "up_to_date",
    }


def _verify_device_access(account: dict, device_id: str) -> JSONResponse | None:
    """Synchronous access check; returns an error response or None when allowed."""
    with connect() as conn:
        if not device_access(conn, account, device_id):
            return err(403, "Device is not bound to this account", 403)
    return None


@router.get("/check")
def app_check_ota(device_id: str, authorization: str = Header(default="")):
    """App-facing OTA check: current version, available version, and selection status.

    Sync def: no await needed, so FastAPI dispatches on the threadpool and the
    short SQLite call does not block the event loop.
    """
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    device_id = device_id.strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
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
