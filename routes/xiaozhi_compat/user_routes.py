"""User and authentication routes for XiaoZhi v1 compatibility API."""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .shared import authorize, ok, err, read_body, connect, now, new_id, str_field, account_payload, make_token

router = APIRouter()


def login_code() -> str:
    """Get login verification code."""
    return os.environ.get("LIMA_XIAOZHI_LOGIN_CODE", "").strip() or "000000"


def validate_login_code(code: str) -> bool:
    """Validate login code."""
    return secrets.compare_digest(code, login_code())


def login_response(row) -> dict | JSONResponse:
    """Build login response with JWT."""
    token = make_token(row)
    if token is None:
        return err(503, "JWT support is unavailable", 503)
    return {
        "token": token,
        "expiresIn": 86400,
        "accountId": row["id"],
        "phone": row["phone"],
    }


@router.post("/login")
async def login(request: Request) -> JSONResponse:
    """手机号+验证码登录，自动注册新用户。"""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    if not phone or not code:
        return err(400, "phone and code are required", 400)
    if not validate_login_code(code):
        return err(401, "Invalid verification code", 401)
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE phone=? AND status='active'", (phone,)).fetchone()
        if row is None:
            account_id = new_id()
            conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)", (account_id, phone, body.get("nickname")))
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    data = login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return ok(data)


@router.post("/auth/register")
async def register(request: Request) -> JSONResponse:
    """Register a phone account with the Phase 0 SMS verification code."""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    if not phone or not code:
        return err(400, "phone and code are required", 400)
    if not validate_login_code(code):
        return err(401, "Invalid verification code", 401)
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE phone=? AND status='active'", (phone,)).fetchone()
        if row is None:
            account_id = new_id()
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
                (account_id, phone, body.get("nickname")),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    data = login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return ok(data)


@router.post("/auth/sms-verification")
async def sms_verification(request: Request) -> JSONResponse:
    """Return the Phase 0 mock SMS code."""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    if not phone:
        return err(400, "phone is required", 400)
    code = login_code()
    return ok({"phone": phone, "code": code, "mock": True, "expiresIn": 300})


@router.get("/auth/me")
async def get_me(authorization: str = Header(default="")) -> JSONResponse:
    """Return the current account from a JWT bearer token."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return ok(account_payload(account))


@router.post("/auth/account/delete")
async def delete_account(authorization: str = Header(default="")) -> JSONResponse:
    """Soft-delete the current account and unbind its active devices."""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    deleted_at = now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE v2_device_binding
            SET status='unbound', unbound_at=?
            WHERE account_id=? AND status='active'
            """,
            (deleted_at, account["id"]),
        )
        conn.execute(
            """
            UPDATE v2_account
            SET status='deleted',
                deleted_at=?,
                nickname='deleted_user',
                phone=NULL,
                wechat_openid=NULL,
                avatar_url=NULL
            WHERE id=?
            """,
            (deleted_at, account["id"]),
        )
        conn.commit()
    return ok({"accountId": account["id"], "deletedAt": deleted_at})
