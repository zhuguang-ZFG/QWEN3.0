"""Device support admin routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from device_support.snapshot import build_support_snapshot

router = APIRouter(prefix="/device/v1/support", tags=["device-support"])


@router.get("/{device_id}/snapshot", dependencies=[Depends(require_private_api_key)])
async def get_support_snapshot(device_id: str):
    """Get a support snapshot for a device (operator diagnostic tool)."""
    snapshot = build_support_snapshot(device_id)
    return JSONResponse(snapshot)
