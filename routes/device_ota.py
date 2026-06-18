"""Device OTA release management routes."""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from access_guard import extract_bearer_token
from device_gateway.auth import validate_device_token
from device_ota.release import ReleaseGate
from device_ota.canary import CanaryDeployment

router = APIRouter(prefix="/device/v1/ota", tags=["device-ota"])
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _state_path() -> str | None:
    return os.environ.get("LIMA_DEVICE_OTA_STATE_PATH") or None


_gate = ReleaseGate(_state_path())
_canary = CanaryDeployment(_state_path())


def reset_ota_state_for_tests() -> None:
    global _gate, _canary
    _gate = ReleaseGate(_state_path())
    _canary = CanaryDeployment(_state_path())


def get_release_gate() -> ReleaseGate:
    return _gate


def get_canary() -> CanaryDeployment:
    return _canary


def _require_device_token(device_id: str, authorization: str) -> None:
    token = extract_bearer_token(authorization)
    if not validate_device_token(device_id, token):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/release/status", dependencies=[Depends(require_private_api_key)])
async def release_status():
    """Check OTA release gate status."""
    return JSONResponse(_gate.get_status())


@router.post("/release/criteria", dependencies=[Depends(require_private_api_key)])
async def set_criteria(name: str, passed: bool):
    """Set a release criterion (admin only)."""
    if not _gate.set_criteria(name, passed):
        raise HTTPException(
            status_code=400,
            detail=f"unknown criterion '{name}'; allowed: {list(_gate.criteria.keys())}",
        )
    return JSONResponse({"ok": True, "name": name, "passed": passed})


@router.post("/deploy/{version}", dependencies=[Depends(require_private_api_key)])
async def deploy_version(version: str, body: dict | None = Body(default=None)):
    """Start deployment of a firmware version.

    Deployment is blocked until the release gate is ready. Canary counters are
    reset when a new version is deployed.
    """
    if not _gate.is_ready():
        raise HTTPException(
            status_code=412,
            detail="release gate not ready; all criteria must pass before deploy",
        )
    firmware = _firmware_metadata(version, body or {})
    _canary.deploy_version(version, firmware)
    return JSONResponse(
        {
            "ok": True,
            "version": version,
            "canary_devices": _canary.canary_devices,
            "firmware": firmware,
        }
    )


@router.get("/canary/status", dependencies=[Depends(require_private_api_key)])
async def canary_status():
    """Check canary deployment health."""
    return JSONResponse(
        {
            "canary_devices": _canary.canary_devices,
            "deployed_version": _canary.deployed_version,
            "success_count": _canary.success_count,
            "failure_count": _canary.failure_count,
            "healthy": _canary.is_healthy(),
        }
    )


@router.post("/canary/devices/{device_id}", dependencies=[Depends(require_private_api_key)])
async def add_canary_device(device_id: str):
    """Add a device to the canary group."""
    _canary.add_canary_device(device_id)
    return JSONResponse({"ok": True, "device_id": device_id})


@router.delete("/canary/devices/{device_id}", dependencies=[Depends(require_private_api_key)])
async def remove_canary_device(device_id: str):
    """Remove a device from the canary group."""
    removed = _canary.remove_canary_device(device_id)
    return JSONResponse({"ok": removed, "device_id": device_id})


@router.post("/canary/record-success/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_canary_success(device_id: str):
    """Record a successful canary deployment for a device."""
    _canary.record_success(device_id)
    return JSONResponse(
        {
            "ok": True,
            "device_id": device_id,
            "success_count": _canary.success_count,
            "failure_count": _canary.failure_count,
            "healthy": _canary.is_healthy(),
        }
    )


@router.post("/canary/record-failure/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_canary_failure(device_id: str):
    """Record a failed canary deployment for a device."""
    _canary.record_failure(device_id)
    return JSONResponse(
        {
            "ok": True,
            "device_id": device_id,
            "success_count": _canary.success_count,
            "failure_count": _canary.failure_count,
            "healthy": _canary.is_healthy(),
        }
    )


@router.post("/upgrade-plan")
async def device_upgrade_plan(body: dict, authorization: str = Header(default="")):
    """Device-facing OTA check endpoint."""
    device_id = str(body.get("device_id") or "").strip()
    current_version = str(body.get("current_version") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    _require_device_token(device_id, authorization)
    firmware = _canary.firmware
    if (
        not _canary.deployed_version
        or current_version == _canary.deployed_version
        or not firmware
        or not _canary.is_canary(device_id)
    ):
        return JSONResponse({"firmware": None})
    return JSONResponse({"firmware": firmware})


@router.post("/install-result")
async def device_install_result(body: dict, authorization: str = Header(default="")):
    """Device-facing OTA install result endpoint."""
    device_id = str(body.get("device_id") or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    _require_device_token(device_id, authorization)
    if not _canary.is_canary(device_id):
        raise HTTPException(status_code=403, detail="device is not in canary rollout")
    success = bool(body.get("success"))
    if success:
        _canary.record_success(device_id)
    else:
        _canary.record_failure(device_id)
    return JSONResponse(
        {
            "ok": True,
            "device_id": device_id,
            "success_count": _canary.success_count,
            "failure_count": _canary.failure_count,
            "healthy": _canary.is_healthy(),
        }
    )


def _firmware_metadata(version: str, body: dict) -> dict[str, str]:
    url = str(body.get("url") or "").strip()
    sha256 = str(body.get("sha256") or "").strip()
    signature = str(body.get("signature") or "").strip()
    if not url and not sha256 and not signature:
        return {}
    if not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="firmware url must use https")
    if not _LOWER_HEX_SHA256.match(sha256):
        raise HTTPException(status_code=400, detail="firmware sha256 must be 64 lowercase hex chars")
    if not signature:
        raise HTTPException(status_code=400, detail="firmware signature is required")
    return {
        "release_id": str(body.get("release_id") or version),
        "version": version,
        "url": url,
        "sha256": sha256,
        "signature": signature,
        "force": str(body.get("force") or "0"),
    }
