"""Admin device gateway management endpoints (extracted from admin_api)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()


@router.get("/api/devices", dependencies=[Depends(verify_admin)])
async def admin_devices():
    """List all connected devices from the device gateway session registry."""
    try:
        from device_gateway.sessions import registry

        sessions_info = []
        with registry._lock:
            for device_id, session in registry._sessions.items():
                sessions_info.append({
                    "device_id": device_id,
                    "fw_rev": session.fw_rev,
                    "capabilities": session.capabilities,
                    "last_uptime_ms": session.last_uptime_ms,
                    "inflight_count": len(session.inflight_tasks),
                })
        return {"devices": sessions_info, "total": len(sessions_info)}
    except (ImportError, AttributeError):
        return {"devices": [], "total": 0, "note": "Device gateway not available"}


@router.get("/api/devices/{device_id}", dependencies=[Depends(verify_admin)])
async def admin_device_detail(device_id: str):
    """Get detailed information about a specific device."""
    try:
        from device_gateway.sessions import registry

        session = registry.get(device_id)
        if session is None:
            raise HTTPException(404, "Device not connected")
        with session.inflight_lock:
            inflight = list(session.inflight_tasks.values())
        return {
            "device_id": device_id,
            "fw_rev": session.fw_rev,
            "capabilities": session.capabilities,
            "last_uptime_ms": session.last_uptime_ms,
            "inflight_tasks": inflight,
        }
    except HTTPException:
        raise
    except (ImportError, AttributeError):
        raise HTTPException(503, "Device gateway not available")


@router.post("/api/devices/{device_id}/restart", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def admin_device_restart(device_id: str):
    """Send a restart command to a connected device."""
    try:
        from device_gateway.sessions import registry

        session = registry.get(device_id)
        if session is None:
            raise HTTPException(404, "Device not connected")
        await session.send_json({"type": "restart", "device_id": device_id})
        return {"device_id": device_id, "command": "restart", "sent": True}
    except HTTPException:
        raise
    except (ImportError, AttributeError):
        raise HTTPException(503, "Device gateway not available")
    except Exception as exc:
        raise HTTPException(500, f"Failed to send restart: {exc}")
