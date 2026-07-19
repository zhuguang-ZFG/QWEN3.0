"""Device status facade for DLC core."""

from __future__ import annotations

from typing import Any

from device_intelligence import shadow_store
from device_gateway.device_status import build_device_status as _build_device_status

# 影子状态白名单：只暴露前端需要的公开字段，剔除 token/mac/password/secret/api_key 等。
SHADOW_WHITELIST: frozenset[str] = frozenset(
    {
        "device_id",
        "fw_rev",
        "capabilities",
        "profile_id",
        "last_heartbeat_uptime_ms",
        "last_motion_event",
        "desired",
        "updated_at",
    }
)


def _sanitize_shadow(shadow: dict[str, Any]) -> dict[str, Any]:
    """Keep only whitelisted keys from the device shadow dict."""
    return {k: v for k, v in shadow.items() if k in SHADOW_WHITELIST}


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
    raw_shadow = shadow_store.snapshot(device_id) or {}
    return {
        "device_id": device_id,
        "online": bool(status.get("online")),
        "working": bool(status.get("working")),
        "active_task_id": status.get("activeTaskId"),
        "firmware_version": status.get("firmwareVersion"),
        "last_seen_at": status.get("lastSeenAt"),
        "shadow": _sanitize_shadow(raw_shadow),
    }
