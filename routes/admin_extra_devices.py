"""Admin API: device gateway inspection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()


@router.get("/api/devices", dependencies=[Depends(verify_admin)])
async def admin_devices():
    """List known devices from device gateway."""
    try:
        from device_gateway.registry import get_all_devices

        devices = get_all_devices()
        return {"devices": devices}
    except (ImportError, AttributeError):
        pass
    try:
        from device_gateway.store import task_store_health

        return {"devices": [], "_note": "task_store only: " + str(task_store_health())}
    except ImportError:
        return {"devices": []}


@router.get("/api/devices/{device_id}", dependencies=[Depends(verify_admin)])
async def admin_device_detail(device_id: str):
    try:
        from device_gateway.registry import get_device

        dev = get_device(device_id)
        if not dev:
            raise HTTPException(404, "Device not found")
        return dev
    except ImportError:
        raise HTTPException(503, "Device gateway not available")


@router.post("/api/devices/{device_id}/restart", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_restart_device(device_id: str):
    try:
        from device_gateway.registry import restart_device

        await restart_device(device_id)
        return {"ok": True, "device_id": device_id}
    except ImportError:
        raise HTTPException(503, "Device gateway not available")
