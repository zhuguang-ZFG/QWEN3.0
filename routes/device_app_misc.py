"""LiMa native device app misc routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from routes.xiaozhi_compat.access import (
    expire_pending_transfers,
    is_owner,
    parse_supply_updates,
)
from routes.xiaozhi_compat.payloads import self_check_payload, supply_payload, transfer_payload
from routes.xiaozhi_compat.shared import (
    authorize,
    connect,
    err,
    expires_at,
    new_id,
    now,
    ok,
    query_int,
    read_body,
    require_device_access,
    str_field,
)

router = APIRouter(prefix="/device/v1/app", tags=["device-app-misc"])


@router.post("/devices/{device_id}/transfer")
async def request_transfer(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    to_phone = str_field(body, "toPhone", "to_phone")
    to_account_id = str_field(body, "toAccountId", "to_account_id")
    reason = str_field(body, "reason") or ""
    with connect() as conn:
        if not is_owner(conn, account, device_id):
            return err(403, "only the device owner can initiate a transfer", 403)
        expire_pending_transfers(conn)
        if to_phone:
            target = conn.execute("SELECT id FROM v2_account WHERE phone=? AND status='active'", (to_phone,)).fetchone()
            if target is None:
                return err(404, "recipient account not found", 404)
            to_account_id = target["id"]
        if not to_account_id:
            return err(400, "toPhone or toAccountId is required", 400)
        if to_account_id == account["id"]:
            return err(400, "cannot transfer to yourself", 400)
        transfer_id = new_id()
        conn.execute(
            "INSERT INTO v2_device_transfer_request (id, device_id, from_account_id, to_account_id, status, reason, expires_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (transfer_id, device_id, account["id"], to_account_id, reason, expires_at(172800)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return transfer_payload(row)


@router.get("/transfers/pending")
async def list_pending_transfers(authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        expire_pending_transfers(conn)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM v2_device_transfer_request WHERE to_account_id=? AND status='pending' ORDER BY created_at DESC",
            (account["id"],),
        ).fetchall()
    return {"transfers": [transfer_payload(row) for row in rows], "count": len(rows)}


@router.post("/transfers/{transfer_id}/accept")
async def accept_transfer(transfer_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        expire_pending_transfers(conn)
        row = conn.execute(
            "SELECT * FROM v2_device_transfer_request WHERE id=? AND status='pending'", (transfer_id,)
        ).fetchone()
        if row is None:
            return err(404, "pending transfer not found or expired", 404)
        if row["to_account_id"] != account["id"]:
            return err(403, "only the recipient can accept this transfer", 403)
        conn.execute(
            "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND bind_mode='owner' AND status='active'",
            (now(), row["device_id"]),
        )
        existing = conn.execute(
            "SELECT id FROM v2_device_binding WHERE device_id=? AND account_id=?", (row["device_id"], account["id"])
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE v2_device_binding SET status='active', bind_mode='owner', unbound_at=NULL WHERE id=?",
                (existing["id"],),
            )
        else:
            conn.execute(
                "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')",
                (new_id(), row["device_id"], account["id"]),
            )
        conn.execute(
            "UPDATE v2_device_transfer_request SET status='accepted', accepted_at=? WHERE id=?", (now(), transfer_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return transfer_payload(row)


@router.post("/transfers/{transfer_id}/cancel")
async def cancel_transfer(transfer_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        expire_pending_transfers(conn)
        row = conn.execute(
            "SELECT * FROM v2_device_transfer_request WHERE id=? AND status='pending'", (transfer_id,)
        ).fetchone()
        if row is None:
            return err(404, "pending transfer not found or expired", 404)
        if row["from_account_id"] != account["id"] and account.get("role") != "admin":
            return err(403, "only the initiator or an admin can cancel", 403)
        conn.execute(
            "UPDATE v2_device_transfer_request SET status='cancelled', cancelled_at=? WHERE id=?", (now(), transfer_id)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return transfer_payload(row)


@router.get("/devices/{device_id}/self-checks")
async def list_self_checks(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    limit = query_int(request.query_params.get("limit"), default=20, minimum=1, maximum=100)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_self_check_event WHERE device_id=? ORDER BY created_at DESC LIMIT ?", (device_id, limit)
        ).fetchall()
    return {"selfChecks": [self_check_payload(row) for row in rows], "count": len(rows)}


@router.put("/devices/{device_id}/supplies")
async def update_supplies(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
    items, error = parse_supply_updates(body)
    if error:
        return error
    with connect() as conn:
        for item in items:
            conn.execute(
                "INSERT INTO v2_device_supply (id, device_id, supply_type, level, status) VALUES (?, ?, ?, ?, ?) ON CONFLICT(device_id, supply_type) DO UPDATE SET level=?, status=?, updated_at=?",
                (
                    new_id(),
                    device_id,
                    item["supply_type"],
                    item["level"],
                    item["status"],
                    item["level"],
                    item["status"],
                    now(),
                ),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM v2_device_supply WHERE device_id=? ORDER BY supply_type", (device_id,)
        ).fetchall()
    return [supply_payload(row) for row in rows]


@router.get("/devices/{device_id}/supplies")
async def get_supplies(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_device_supply WHERE device_id=? ORDER BY supply_type", (device_id,)
        ).fetchall()
    return {"supplies": [supply_payload(row) for row in rows], "count": len(rows)}
