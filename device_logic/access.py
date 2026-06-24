"""Device access checks and supply parsing."""

from __future__ import annotations

from typing import Any

import sqlite3
from fastapi.responses import JSONResponse

from device_logic.http import err, now, str_field


def device_access(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
    if account.get("role") == "admin":
        return True
    row = conn.execute(
        "SELECT 1 FROM v2_device_binding WHERE device_id=? AND account_id=? AND status='active'",
        (device_id, account["id"]),
    ).fetchone()
    return row is not None


def check_share_permission(
    conn: sqlite3.Connection,
    device_id: str,
    account_id: str,
    required: str = "view",
) -> bool:
    """Return True when an accepted, unexpired share grants *required* permission."""
    if required not in {"view", "control"}:
        return False
    row = conn.execute(
        """
        SELECT permission FROM v2_device_share
        WHERE device_id=? AND guest_account_id=? AND status='accepted' AND expires_at > ?
        """,
        (device_id, account_id, now()),
    ).fetchone()
    if row is None:
        return False
    permission = row["permission"]
    if required == "control":
        return permission == "control"
    return permission in {"view", "control"}


def require_device_access(
    conn: sqlite3.Connection,
    account: dict[str, Any],
    device_id: str,
) -> JSONResponse | None:
    if not device_access(conn, account, device_id):
        return err(403, "Device is not bound to this account", 403)
    return None


def require_device_control(
    conn: sqlite3.Connection,
    account: dict[str, Any],
    device_id: str,
) -> JSONResponse | None:
    """Require owner or an accepted 'control' share for the device."""
    if is_owner(conn, account, device_id):
        return None
    if check_share_permission(conn, device_id, account["id"], "control"):
        return None
    return err(403, "control permission required", 403)


def is_owner(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
    if account.get("role") == "admin":
        return True
    row = conn.execute(
        """
        SELECT 1 FROM v2_device_binding
        WHERE device_id=? AND account_id=? AND bind_mode='owner' AND status='active'
        """,
        (device_id, account["id"]),
    ).fetchone()
    return row is not None


def expire_pending_transfers(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE v2_device_transfer_request SET status='expired' WHERE status='pending' AND expires_at <= ?",
        (now(),),
    )


def parse_supply_updates(body: dict[str, Any]) -> tuple[list[dict[str, Any]], JSONResponse | None]:
    raw_items: list[dict[str, Any]] = []
    if isinstance(body.get("supplies"), list):
        raw_items.extend(item for item in body["supplies"] if isinstance(item, dict))
    direct_type = str_field(body, "supplyType", "supply_type")
    if direct_type:
        raw_items.append(body)
    for supply_type in ("pen", "paper", "battery"):
        value = body.get(supply_type)
        if isinstance(value, dict):
            raw_items.append({"supplyType": supply_type, **value})
    updates: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        supply_type = str_field(item, "supplyType", "supply_type")
        status = str_field(item, "status") or "unknown"
        if not supply_type:
            return [], err(400, "supplyType is required", 400)
        if status not in {"normal", "low", "empty", "unknown"}:
            return [], err(400, "invalid supply status", 400)
        try:
            level = float(item.get("level", 1.0))
        except (TypeError, ValueError):
            return [], err(400, "supply level must be numeric", 400)
        if not 0.0 <= level <= 1.0:
            return [], err(400, "supply level must be between 0.0 and 1.0", 400)
        updates[supply_type] = {"supply_type": supply_type, "level": level, "status": status}
    if not updates:
        return [], err(400, "at least one supply update is required", 400)
    return list(updates.values()), None
