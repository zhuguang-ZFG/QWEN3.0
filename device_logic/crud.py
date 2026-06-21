"""Device CRUD shared by native /device/v1/app and xiaozhi compat routes."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from device_logic.device_sn import validate_device_sn
from device_logic.errors import DeviceLogicError
from device_logic.updates import parse_device_updates, sql_set_clause


def _json_metadata(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, str):
        return value
    return None


def _get_or_create_device(
    conn: sqlite3.Connection,
    *,
    device_sn: str,
    model: str,
    firmware_ver: str,
    hardware_ver: str,
    metadata: Any,
    new_id,
) -> sqlite3.Row:
    device = conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (device_sn,)).fetchone()
    if device is not None:
        return device
    device_id = new_id()
    conn.execute(
        """
        INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            device_sn,
            model or "esp32s3_xyz",
            firmware_ver or "",
            hardware_ver or "",
            _json_metadata(metadata),
        ),
    )
    row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        raise DeviceLogicError(500, "device insert failed", 500)
    return row


def _ensure_owner_binding(conn: sqlite3.Connection, *, device_id: str, account_id: str, new_id) -> str:
    binding = conn.execute(
        "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
        (device_id, account_id),
    ).fetchone()
    if binding is None:
        binding_id = new_id()
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES (?, ?, ?, 'owner', 'active')
            """,
            (binding_id, device_id, account_id),
        )
        return binding_id
    binding_id = binding["id"]
    conn.execute("UPDATE v2_device_binding SET status='active', unbound_at=NULL WHERE id=?", (binding_id,))
    return binding_id


def bind_device(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    device_sn: str,
    model: str,
    firmware_ver: str,
    hardware_ver: str,
    metadata: Any,
    new_id,
) -> dict[str, Any]:
    device_sn = validate_device_sn(device_sn)
    owner = conn.execute(
        """
        SELECT account_id
        FROM v2_device_binding
        WHERE device_id=(SELECT id FROM v2_device WHERE device_sn=?)
          AND bind_mode='owner'
          AND status='active'
        """,
        (device_sn,),
    ).fetchone()
    if owner is not None and owner["account_id"] != account_id:
        raise DeviceLogicError(4005, "Device is already bound", 400)

    device = _get_or_create_device(
        conn,
        device_sn=device_sn,
        model=model,
        firmware_ver=firmware_ver,
        hardware_ver=hardware_ver,
        metadata=metadata,
        new_id=new_id,
    )
    binding_id = _ensure_owner_binding(conn, device_id=device["id"], account_id=account_id, new_id=new_id)
    conn.commit()
    return {"binding_id": binding_id, "device_id": device["id"], "device": device}


def list_device_rows(conn: sqlite3.Connection, *, account_id: str, role: str) -> list[sqlite3.Row]:
    if role == "admin":
        return conn.execute("SELECT * FROM v2_device ORDER BY created_at DESC").fetchall()
    return conn.execute(
        """
        SELECT d.*
        FROM v2_device d
        JOIN v2_device_binding b ON b.device_id = d.id
        WHERE b.account_id=? AND b.status='active'
        ORDER BY b.bound_at DESC
        """,
        (account_id,),
    ).fetchall()


def get_device_row(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()


def update_device_row(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    body: dict[str, Any],
) -> sqlite3.Row:
    updates = parse_device_updates(body)
    assignments, values = sql_set_clause(updates)
    result = conn.execute(f"UPDATE v2_device SET {assignments} WHERE id=?", (*values, device_id))
    conn.commit()
    if result.rowcount < 1:
        raise DeviceLogicError(404, "device not found", 404)
    row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        raise DeviceLogicError(404, "device not found", 404)
    return row


def unbind_device(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    account_id: str,
    role: str,
    now,
) -> None:
    if role == "admin":
        result = conn.execute(
            "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND status='active'",
            (now(), device_id),
        )
    else:
        result = conn.execute(
            """
            UPDATE v2_device_binding
            SET status='unbound', unbound_at=?
            WHERE device_id=? AND account_id=? AND status='active'
            """,
            (now(), device_id, account_id),
        )
    conn.commit()
    if result.rowcount < 1:
        raise DeviceLogicError(404, "active binding not found", 404)


def manual_add_device(
    conn: sqlite3.Connection,
    *,
    device_sn: str,
    model: str,
    firmware_ver: str,
    hardware_ver: str,
    metadata: Any,
    new_id,
) -> sqlite3.Row:
    device_sn = validate_device_sn(device_sn)
    existing = conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (device_sn,)).fetchone()
    if existing is not None:
        raise DeviceLogicError(409, "device with this serial number already exists", 409)
    device_id = new_id()
    conn.execute(
        """
        INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver, metadata)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            device_sn,
            model or "esp32s3_xyz",
            firmware_ver or "",
            hardware_ver or "",
            _json_metadata(metadata),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        raise DeviceLogicError(500, "device insert failed", 500)
    return row
