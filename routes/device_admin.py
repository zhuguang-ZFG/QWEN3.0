"""Device admin routes: health scoring and predictive maintenance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from device_gateway.health_score import DeviceHealthScore
from device_gateway.maintenance import PredictiveMaintenance
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err

router = APIRouter(prefix="/admin", tags=["device-admin"])


def _require_admin(authorization: str) -> dict[str, Any] | JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    if account.get("role") != "admin":
        return err(403, "only admin can access device health", 403)
    return account


@router.get("/devices/{device_id}/health")
async def get_device_health(device_id: str, authorization: str = Header(default="")) -> Any:
    account = _require_admin(authorization)
    if isinstance(account, JSONResponse):
        return account

    with connect() as conn:
        row = conn.execute("SELECT 1 FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        return err(404, "device not found", 404)

    health = DeviceHealthScore().compute(device_id)
    maintenance = PredictiveMaintenance().analyze_trend(device_id)
    return {
        "deviceId": device_id,
        "health": health,
        "maintenance": maintenance,
    }
