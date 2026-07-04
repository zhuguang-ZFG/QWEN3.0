"""Device status facade for DLC core."""

from __future__ import annotations

from typing import Any

from device_intelligence import shadow_store
from routes.device_app_api import _build_device_status


async def get_device_status(device_id: str) -> dict[str, Any]:
    """Aggregate the canonical runtime device status for DLC callers.

    Returns:
        {
            "device_id": str,
            "online": bool,
            "working": bool,
            "active_task_id": str | None,
            "firmware_version": str | None,
            "last_seen_at": str | None,
            "shadow": dict,
        }
    """
    status = _build_device_status(device_id)
    return {
        "device_id": device_id,
        "online": bool(status.get("online")),
        "working": bool(status.get("working")),
        "active_task_id": status.get("activeTaskId"),
        "firmware_version": status.get("firmwareVersion"),
        "last_seen_at": status.get("lastSeenAt"),
        "shadow": shadow_store.snapshot(device_id) or {},
    }
