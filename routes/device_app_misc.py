"""LiMa native device app misc routes."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from device_logic.access import (
    expire_pending_transfers,
    is_owner,
    parse_supply_updates,
    require_device_access,
)
from device_logic.auth import authorize
from device_logic.crud import bind_device
from device_logic.db import connect
from device_logic.errors import DeviceLogicError
from device_logic.http import err, expires_at, new_id, now, query_int, read_body, str_field
from device_logic.payloads import self_check_payload, supply_payload, transfer_payload

router = APIRouter(prefix="/device/v1/app", tags=["device-app-misc"])


@router.post("/devices/{device_id}/transfer")
async def request_transfer(device_id: str, request: Request, authorization: str = Header(default="")) -> Any:
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
async def list_pending_transfers(authorization: str = Header(default="")) -> Any:
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
async def accept_transfer(transfer_id: str, authorization: str = Header(default="")) -> Any:
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
async def cancel_transfer(transfer_id: str, authorization: str = Header(default="")) -> Any:
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
async def list_self_checks(device_id: str, request: Request, authorization: str = Header(default="")) -> Any:
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
async def update_supplies(device_id: str, request: Request, authorization: str = Header(default="")) -> Any:
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
async def get_supplies(device_id: str, authorization: str = Header(default="")) -> Any:
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


@router.post("/devices/provision")
async def create_provision(request: Request, authorization: str = Header(default="")) -> Any:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_sn = str_field(body, "deviceSn", "device_sn")
    wifi_ssid = str_field(body, "wifiSsid", "ssid")
    wifi_password = str_field(body, "wifiPassword", "password") or ""
    if not device_sn:
        return err(400, "deviceSn is required", 400)
    if not wifi_ssid:
        return err(400, "wifiSsid is required", 400)

    provision_id = new_id()
    provision_token = secrets.token_urlsafe(32)
    server_url = f"wss://{request.headers.get('host') or 'chat.donglicao.com'}/device/v1/ws"
    expires = expires_at(1800)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_pair_request
            (id, pair_token, device_sn, account_id, wifi_ssid, server_url, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (provision_id, provision_token, device_sn, account["id"], wifi_ssid, server_url, expires),
        )
        conn.commit()

    return {
        "provisionId": provision_id,
        "provisionToken": provision_token,
        "deviceSn": device_sn,
        "serverUrl": server_url,
        "protocol": "lima-device-v1",
        "expiresIn": 1800,
        "configPayload": {
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
            "server_url": server_url,
            "pair_token": provision_token,
            "device_sn": device_sn,
        },
    }


@router.post("/devices/provision/confirm")
async def confirm_provision(request: Request) -> Any:
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    token = str_field(body, "provisionToken", "pair_token")
    device_sn = str_field(body, "deviceSn", "device_sn")
    if not token:
        return err(400, "provisionToken is required", 400)
    if not device_sn:
        return err(400, "deviceSn is required", 400)

    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_pair_request WHERE pair_token=? AND status='pending'", (token,)).fetchone()
        if row is None:
            return err(404, "provision token not found", 404)
        if row["expires_at"] < now():
            conn.execute("UPDATE v2_pair_request SET status='expired' WHERE id=?", (row["id"],))
            conn.commit()
            return err(400, "provision token expired", 400)
        if row["device_sn"] != device_sn:
            return err(400, "deviceSn does not match provision token", 400)
        account_id = row["account_id"]
        pair_request_id = row["id"]

        try:
            bind_device(
                conn,
                account_id=account_id,
                device_sn=device_sn,
                model="esp32s3_xyz",
                firmware_ver="",
                hardware_ver="",
                metadata=None,
                new_id=new_id,
            )
        except DeviceLogicError as exc:
            return err(exc.code, exc.message, exc.http_status)

        conn.execute("UPDATE v2_pair_request SET status='completed' WHERE id=?", (pair_request_id,))
        conn.commit()

    return {"deviceSn": device_sn, "status": "bound", "accountId": account_id}
