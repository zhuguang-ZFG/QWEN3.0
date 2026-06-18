"""LiMa native device app member and voiceprint routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from routes.xiaozhi_compat.constants import ALLOWED_MEMBER_ROLES
from routes.xiaozhi_compat.payloads import member_payload, voiceprint_payload
from routes.xiaozhi_compat.shared import (
    authorize,
    connect,
    err,
    new_id,
    ok,
    read_body,
    require_device_access,
    str_field,
)

router = APIRouter(prefix="/device/v1/app", tags=["device-app-members"])


@router.post("/members")
async def create_member(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_id = str_field(body, "deviceId", "device_id")
    name = str_field(body, "name")
    role = str_field(body, "role") or "child"
    if not device_id or not name:
        return err(400, "deviceId and name are required", 400)
    if role not in ALLOWED_MEMBER_ROLES:
        return err(400, "invalid member role", 400)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        member_id = new_id()
        conn.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name, role, avatar_url) VALUES (?, ?, ?, ?, ?, ?)",
            (member_id, account["id"], device_id, name, role, body.get("avatarUrl") or body.get("avatar_url")),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_member WHERE id=?", (member_id,)).fetchone()
    return member_payload(row)


@router.get("/devices/{device_id}/members")
async def list_members(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute(
            "SELECT * FROM v2_member WHERE device_id=? AND status='active' ORDER BY created_at ASC",
            (device_id,),
        ).fetchall()
    return {"members": [member_payload(row) for row in rows], "count": len(rows)}


@router.post("/voiceprints/enroll")
async def enroll_voiceprint(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    member_id = str_field(body, "memberId", "member_id")
    device_id = str_field(body, "deviceId", "device_id")
    if not member_id or not device_id:
        return err(400, "memberId and deviceId are required", 400)
    with connect() as conn:
        denied = require_device_access(conn, account, device_id)
        if denied:
            return denied
        member = conn.execute(
            "SELECT * FROM v2_member WHERE id=? AND device_id=? AND status='active'",
            (member_id, device_id),
        ).fetchone()
        if member is None:
            return err(404, "member not found", 404)
        row = conn.execute(
            "SELECT * FROM v2_voiceprint WHERE member_id=? AND device_id=? AND status!='disabled'",
            (member_id, device_id),
        ).fetchone()
        if row is None:
            voiceprint_id = new_id()
            conn.execute(
                "INSERT INTO v2_voiceprint (id, member_id, device_id, status) VALUES (?, ?, ?, 'verifying')",
                (voiceprint_id, member_id, device_id),
            )
            conn.execute("UPDATE v2_member SET voiceprint_id=? WHERE id=?", (voiceprint_id, member_id))
            conn.commit()
            row = conn.execute("SELECT * FROM v2_voiceprint WHERE id=?", (voiceprint_id,)).fetchone()
    return voiceprint_payload(row, member["name"])


@router.delete("/voiceprints/{voiceprint_id}")
async def delete_voiceprint(voiceprint_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_voiceprint WHERE id=? AND status!='disabled'", (voiceprint_id,)).fetchone()
        if row is None:
            return err(404, "voiceprint not found", 404)
        denied = require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute("UPDATE v2_voiceprint SET status='disabled' WHERE id=?", (voiceprint_id,))
        conn.execute("UPDATE v2_member SET voiceprint_id=NULL WHERE voiceprint_id=?", (voiceprint_id,))
        conn.commit()
    return {"voiceprintId": voiceprint_id, "status": "disabled"}
