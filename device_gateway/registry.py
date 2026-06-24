"""Device gateway registry for admin inspection.

Provides a read-only view of persisted devices plus the ability to send a
restart command to an online device session. This module intentionally stays
thin: device ownership and persistence live in ``device_logic/crud.py`` and
``device_logic/db.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from device_gateway.sessions import registry as session_registry
from device_logic.crud import get_device_row, list_device_rows
from device_logic.db import connect
from device_logic.http import now

_log = logging.getLogger(__name__)


def _device_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLite device row to a plain dictionary."""
    return {
        "id": row["id"],
        "device_sn": row["device_sn"],
        "model": row["model"],
        "firmware_ver": row["firmware_ver"],
        "hardware_ver": row["hardware_ver"],
        "metadata": row["metadata"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _enrich_online(device: dict[str, Any]) -> dict[str, Any]:
    """Add online status from the in-memory session registry."""
    session = session_registry.get(device["id"])
    device["online"] = session is not None
    if session is not None:
        device["last_seen"] = session.connected_at
        device["fw_rev"] = session.fw_rev
        device["capabilities"] = list(session.capabilities)
    return device


def get_all_devices() -> list[dict[str, Any]]:
    """Return all persisted devices, enriched with online status."""
    with connect() as conn:
        rows = list_device_rows(conn, account_id="", role="admin")
        return [_enrich_online(_device_dict(row)) for row in rows]


def get_device(device_id: str) -> dict[str, Any] | None:
    """Return a single device with online status and owner bindings."""
    with connect() as conn:
        row = get_device_row(conn, device_id)
        if row is None:
            return None
        device = _enrich_online(_device_dict(row))

        owners = conn.execute(
            """
            SELECT a.id, a.nickname, a.phone, b.bind_mode, b.status, b.bound_at
            FROM v2_device_binding b
            JOIN v2_account a ON a.id = b.account_id
            WHERE b.device_id = ? AND b.status = 'active'
            ORDER BY b.bound_at DESC
            """,
            (device_id,),
        ).fetchall()
        device["owners"] = [
            {
                "account_id": o["id"],
                "nickname": o["nickname"],
                "phone": o["phone"],
                "bind_mode": o["bind_mode"],
                "bound_at": o["bound_at"],
            }
            for o in owners
        ]
        return device


async def restart_device(device_id: str) -> dict[str, Any]:
    """Request an online device to restart.

    If the device has an active WebSocket session, send the restart command
    directly. Otherwise queue the command for the next time the device connects
    by creating a system restart task in the device task store.
    """
    session = session_registry.get(device_id)
    if session is not None:
        try:
            await session.send_json(
                {
                    "type": "system/restart",
                    "device_id": device_id,
                    "ts": now(),
                }
            )
            return {"ok": True, "device_id": device_id, "delivered": True}
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("failed to send restart to %s: %s", device_id, exc)

    # Fallback: enqueue a restart task for next connect.
    try:
        from device_gateway.tasks import enqueue_pending_task
        from device_gateway.store import task_store

        task = {
            "task_id": f"restart-{device_id}-{now()}",
            "device_id": device_id,
            "type": "system/restart",
            "payload": {},
            "created_at": now(),
        }
        enqueue_pending_task(device_id, task)
        return {"ok": True, "device_id": device_id, "delivered": False, "queued": True}
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("failed to queue restart for %s: %s", device_id, exc)
        raise RuntimeError(f"device {device_id} is offline and restart could not be queued") from exc
