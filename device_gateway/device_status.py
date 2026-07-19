"""Canonical runtime device status payload.

Sunk from routes/device_app_api.py (2026-07-20 review W10): dlc_core was
importing a private function upward from the routes layer, inverting the
documented dependency chain (routes/dlc_api → dlc_core → device_gateway).
Both routes and dlc_core now import from here.
"""

from __future__ import annotations

from typing import Any

from device_gateway.sessions import registry
from device_gateway.tasks import active_tasks_for_device
from device_logic.http import now


def build_device_status(device_id: str) -> dict[str, Any]:
    """Build the canonical device status payload used by REST and WebSocket."""
    session = registry.get(device_id)
    tasks = active_tasks_for_device(device_id)
    active_task_id = tasks[0].get("task_id") if tasks else None
    online = session is not None
    connected_at: str | None = None
    firmware_version: str | None = None
    protocol_version: str | None = None
    last_seen_at: str | None = None
    if session is not None:
        connected_at = getattr(session, "connected_at", None) or None
        firmware_version = session.fw_rev or None
        protocol_version = session.protocol_version or None
        last_seen_at = now()
    return {
        "deviceId": device_id,
        "online": online,
        "connectedAt": connected_at,
        "working": bool(active_task_id),
        "activeTaskId": active_task_id,
        "firmwareVersion": firmware_version,
        "protocolVersion": protocol_version,
        "lastSeenAt": last_seen_at,
    }
