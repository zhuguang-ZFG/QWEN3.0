"""Device OTA release management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_ota.release import ReleaseGate
from device_ota.canary import CanaryDeployment

router = APIRouter(prefix="/device/v1/ota", tags=["device-ota"])

_gate = ReleaseGate()
_canary = CanaryDeployment()


def get_release_gate() -> ReleaseGate:
    return _gate


def get_canary() -> CanaryDeployment:
    return _canary


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
async def deploy_version(version: str):
    """Start deployment of a firmware version.

    Deployment is blocked until the release gate is ready. Canary counters are
    reset when a new version is deployed.
    """
    if not _gate.is_ready():
        raise HTTPException(
            status_code=412,
            detail="release gate not ready; all criteria must pass before deploy",
        )
    _canary.deploy_version(version)
    return JSONResponse({
        "ok": True,
        "version": version,
        "canary_devices": _canary.canary_devices,
    })


@router.get("/canary/status", dependencies=[Depends(require_private_api_key)])
async def canary_status():
    """Check canary deployment health."""
    return JSONResponse({
        "canary_devices": _canary.canary_devices,
        "deployed_version": _canary.deployed_version,
        "success_count": _canary.success_count,
        "failure_count": _canary.failure_count,
        "healthy": _canary.is_healthy(),
    })


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
    return JSONResponse({
        "ok": True,
        "device_id": device_id,
        "success_count": _canary.success_count,
        "failure_count": _canary.failure_count,
        "healthy": _canary.is_healthy(),
    })


@router.post("/canary/record-failure/{device_id}", dependencies=[Depends(require_private_api_key)])
async def record_canary_failure(device_id: str):
    """Record a failed canary deployment for a device."""
    _canary.record_failure(device_id)
    return JSONResponse({
        "ok": True,
        "device_id": device_id,
        "success_count": _canary.success_count,
        "failure_count": _canary.failure_count,
        "healthy": _canary.is_healthy(),
    })
