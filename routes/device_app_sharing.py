"""LiMa device sharing and guest-mode routes."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.access import check_share_permission, is_owner
from device_logic.auth import authorize
from device_logic.db import connect
from device_logic.http import err, expires_at, new_id, now, read_body, str_field
from device_logic.payloads import device_payload, share_payload

router = APIRouter(prefix="/device/v1/app", tags=["device-app-sharing"])


def _share_token() -> str:
    return secrets.token_urlsafe(32)


def _require_owner(conn: Any, account: dict[str, Any], device_id: str) -> JSONResponse | None:
    if not is_owner(conn, account, device_id):
        return err(403, "only the device owner can manage shares", 403)
    return None


def _parse_permission(body: dict[str, Any]) -> str | None:
    permission = str_field(body, "permission") or "view"
    if permission not in {"view", "control"}:
        return None
    return permission


def _parse_expires_at(body: dict[str, Any]) -> str | None:
    explicit = str_field(body, "expiresAt", "expires_at")
    if explicit:
        return explicit
    try:
        seconds = int(body.get("expiresIn", 604800))
    except (TypeError, ValueError):
        seconds = 604800
    return expires_at(max(60, seconds))


@router.post("/devices/{device_id}/share")
async def create_share(device_id: str, request: Request, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    permission = _parse_permission(body)
    if permission is None:
        return err(400, "permission must be 'view' or 'control'", 400)
    expires = _parse_expires_at(body)
    if expires is None:
        return err(400, "invalid expiresAt", 400)
    with connect() as conn:
        denied = _require_owner(conn, account, device_id)
        if denied:
            return denied
        share_id = new_id()
        token = _share_token()
        conn.execute(
            """
            INSERT INTO v2_device_share
            (id, device_id, owner_account_id, share_token, permission, status, expires_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (share_id, device_id, account["id"], token, permission, expires),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_share WHERE id=?", (share_id,)).fetchone()
    return share_payload(row)


@router.post("/devices/{device_id}/share/revoke")
async def revoke_share(device_id: str, request: Request, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    share_token = str_field(body, "shareToken", "share_token")
    share_id = str_field(body, "shareId", "share_id")
    if not share_token and not share_id:
        return err(400, "shareToken or shareId is required", 400)
    with connect() as conn:
        denied = _require_owner(conn, account, device_id)
        if denied:
            return denied
        if share_token:
            row = conn.execute(
                "SELECT * FROM v2_device_share WHERE share_token=? AND device_id=?",
                (share_token, device_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM v2_device_share WHERE id=? AND device_id=?",
                (share_id, device_id),
            ).fetchone()
        if row is None:
            return err(404, "share not found", 404)
        if row["status"] not in {"pending", "accepted"}:
            return err(400, "share is already inactive", 400)
        conn.execute(
            "UPDATE v2_device_share SET status='revoked', revoked_at=? WHERE id=?",
            (now(), row["id"]),
        )
        if row["guest_account_id"]:
            conn.execute(
                """
                UPDATE v2_device_binding
                SET status='unbound', unbound_at=?
                WHERE device_id=? AND account_id=? AND bind_mode='shared' AND status='active'
                """,
                (now(), device_id, row["guest_account_id"]),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_share WHERE id=?", (row["id"],)).fetchone()
    return share_payload(row)


@router.post("/shares/{share_token}/accept")
async def accept_share(share_token: str, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_device_share WHERE share_token=? AND status='pending'",
            (share_token,),
        ).fetchone()
        if row is None:
            return err(404, "share not found or already accepted/revoked", 404)
        if row["expires_at"] <= now():
            conn.execute(
                "UPDATE v2_device_share SET status='expired' WHERE id=?",
                (row["id"],),
            )
            conn.commit()
            return err(400, "share token expired", 400)
        if row["owner_account_id"] == account["id"]:
            return err(400, "owner cannot accept their own share", 400)
        device_id = row["device_id"]
        existing = conn.execute(
            "SELECT id FROM v2_device_binding WHERE device_id=? AND account_id=?",
            (device_id, account["id"]),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE v2_device_binding SET status='active', bind_mode='shared', unbound_at=NULL WHERE id=?",
                (existing["id"],),
            )
        else:
            conn.execute(
                """
                INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
                VALUES (?, ?, ?, 'shared', 'active')
                """,
                (new_id(), device_id, account["id"]),
            )
        conn.execute(
            """
            UPDATE v2_device_share
            SET status='accepted', guest_account_id=?, accepted_at=?
            WHERE id=?
            """,
            (account["id"], now(), row["id"]),
        )
        conn.commit()
        device = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
        share = conn.execute("SELECT * FROM v2_device_share WHERE id=?", (row["id"],)).fetchone()
    return {"device": device_payload(device), "share": share_payload(share)}


@router.get("/devices/{device_id}/shares")
async def list_shares(device_id: str, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = _require_owner(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_device_share WHERE device_id=? ORDER BY created_at DESC",
            (device_id,),
        ).fetchall()
    return {"shares": [share_payload(row) for row in rows], "count": len(rows)}
