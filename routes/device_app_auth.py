"""LiMa native device app auth routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from config.env import wechat_dev_login_enabled, xiaozhi_dev_static_login_code_enabled
from fastapi.responses import JSONResponse

from device_logic.auth import account_payload, authorize, make_token
from device_logic.auth_rate import allow_device_auth
from device_logic.db import connect
from device_logic.http import err, new_id, now, read_body, str_field
from device_logic.sms import login_code_error, sms_verification_payload, validate_login_code
from routes.request_tracking import client_ip

router = APIRouter(prefix="/device/v1/app", tags=["device-app-auth"])


def _static_login_code_error() -> JSONResponse | None:
    if xiaozhi_dev_static_login_code_enabled():
        return login_code_error()
    return err(503, "Static SMS verification code is disabled outside dev mode", 503)


def _login_response(row):
    token = make_token(row)
    if token is None:
        return err(503, "JWT support is unavailable", 503)
    return {
        "token": token,
        "expiresIn": 86400,
        "accountId": row["id"],
        "userId": row["id"],
        "phone": row["phone"],
    }


def _wechat_openid_from_code(code: str) -> str:
    if not wechat_dev_login_enabled():
        return ""
    return f"wx:{code}"


@router.post("/auth/login")
async def login(request: Request):
    if not allow_device_auth("login", client_ip(request)):
        return err(429, "Too many login attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    if not code:
        return err(400, "code is required", 400)
    if not phone:
        openid = _wechat_openid_from_code(code)
        if not openid:
            return err(503, "WeChat login is not configured", 503)
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM v2_account WHERE wechat_openid=? AND status='active'",
                (openid,),
            ).fetchone()
            if row is None:
                account_id = new_id()
                conn.execute(
                    "INSERT INTO v2_account (id, wechat_openid, nickname) VALUES (?, ?, ?)",
                    (account_id, openid, body.get("nickname") or "wechat-user"),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
        data = _login_response(row)
        if isinstance(data, JSONResponse):
            return data
        return data
    config_error = _static_login_code_error()
    if config_error:
        return config_error
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
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return data


@router.post("/auth/register")
async def register(request: Request):
    if not allow_device_auth("register", client_ip(request)):
        return err(429, "Too many registration attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    if not phone or not code:
        return err(400, "phone and code are required", 400)
    config_error = _static_login_code_error()
    if config_error:
        return config_error
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
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return data


@router.post("/auth/sms-verification")
async def sms_verification(request: Request):
    if not allow_device_auth("sms", client_ip(request)):
        return err(429, "Too many SMS verification requests", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    if not phone:
        return err(400, "phone is required", 400)
    config_error = _static_login_code_error()
    if config_error:
        return config_error
    return sms_verification_payload(phone)


@router.get("/auth/me")
async def get_me(authorization: str = Header(default="")):
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return account_payload(account)


@router.post("/auth/account/delete")
async def delete_account(authorization: str = Header(default="")):
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
    return {"accountId": account["id"], "deletedAt": deleted_at}
