"""LiMa native device app auth routes."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Header, Request, Response

from config.env import wechat_dev_login_enabled, xiaozhi_dev_static_login_code_enabled
from fastapi.responses import JSONResponse

from device_logic.auth import (
    _hash_password,
    _verify_password,
    account_payload,
    authorize,
    make_token,
)
from device_logic.auth_rate import allow_device_auth
from device_logic.captcha import create_captcha, generate_captcha_image
from device_logic.db import connect
from device_logic.http import err, new_id, now, read_body, str_field
from device_logic.sms import login_code_error, sms_verification_payload, validate_login_code
from routes.request_tracking import client_ip

router = APIRouter(prefix="/device/v1/app", tags=["device-app-auth"])


def _static_login_code_error() -> JSONResponse | None:
    if xiaozhi_dev_static_login_code_enabled():
        return login_code_error()
    return err(503, "Static SMS verification code is disabled outside dev mode", 503)


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


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
        "email": row["email"],
    }


def _is_valid_email(value: str) -> bool:
    return bool(value and _EMAIL_RE.match(value))


def _account_by_email(email: str) -> Any | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM v2_account WHERE email=? AND status='active'", (email,)
        ).fetchone()


def _wechat_openid_from_code(code: str) -> str:
    if not wechat_dev_login_enabled():
        return ""
    return f"wx:{code}"


def _find_or_create_wechat_account(openid: str, nickname: str | None) -> Any:
    """Look up an active account by WeChat openid, creating one if absent."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_account WHERE wechat_openid=? AND status='active'",
            (openid,),
        ).fetchone()
        if row is None:
            account_id = new_id()
            conn.execute(
                "INSERT INTO v2_account (id, wechat_openid, nickname) VALUES (?, ?, ?)",
                (account_id, openid, nickname or "wechat-user"),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    return row


def _find_or_create_phone_account(phone: str, nickname: str | None) -> Any:
    """Look up an active account by phone, creating one if absent."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE phone=? AND status='active'", (phone,)).fetchone()
        if row is None:
            account_id = new_id()
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
                (account_id, phone, nickname),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    return row


async def _login_by_wechat(body: dict) -> dict | JSONResponse:
    """Handle WeChat-code login path."""
    code = str_field(body, "code", "smsCode")
    openid = _wechat_openid_from_code(code)
    if not openid:
        return err(503, "WeChat login is not configured", 503)
    row = _find_or_create_wechat_account(openid, body.get("nickname"))
    return _login_response(row)


async def _login_by_phone(body: dict) -> dict | JSONResponse:
    """Handle SMS-code login path."""
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    config_error = _static_login_code_error()
    if config_error:
        return config_error
    if not phone or not code:
        return err(400, "phone and code are required", 400)
    if not validate_login_code(code):
        return err(401, "Invalid verification code", 401)
    row = _find_or_create_phone_account(phone, body.get("nickname"))
    return _login_response(row)


@router.post("/auth/login")
async def login(request: Request):
    if not allow_device_auth("login", client_ip(request)):
        return err(429, "Too many login attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    code = str_field(body, "code", "smsCode")
    if not code:
        return err(400, "code is required", 400)
    phone = str_field(body, "phone", "mobile")
    if not phone:
        data = await _login_by_wechat(body)
    else:
        data = await _login_by_phone(body)
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


@router.post("/auth/register-email")
async def register_email(request: Request):
    if not allow_device_auth("register", client_ip(request)):
        return err(429, "Too many registration attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    email = str_field(body, "email")
    password = str_field(body, "password")
    if not _is_valid_email(email):
        return err(400, "A valid email is required", 400)
    if not password or len(password) < 6:
        return err(400, "password must be at least 6 characters", 400)
    if _account_by_email(email):
        return err(409, "Email already registered", 409)
    account_id = new_id()
    with connect() as conn:
        conn.execute(
            "INSERT INTO v2_account (id, email, password_hash, nickname) VALUES (?, ?, ?, ?)",
            (account_id, email, _hash_password(password), body.get("nickname") or email.split("@")[0]),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return data


@router.post("/auth/login-email")
async def login_email(request: Request):
    if not allow_device_auth("login", client_ip(request)):
        return err(429, "Too many login attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    email = str_field(body, "email")
    password = str_field(body, "password")
    if not _is_valid_email(email):
        return err(400, "A valid email is required", 400)
    if not password:
        return err(400, "password is required", 400)
    row = _account_by_email(email)
    if row is None or not _verify_password(password, row.get("password_hash")):
        return err(401, "Invalid email or password", 401)
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


@router.get("/auth/captcha")
async def get_captcha() -> Response:
    """返回 PNG 图形验证码。"""
    captcha_id, code = create_captcha()
    image_bytes = generate_captcha_image(code)
    if image_bytes is None:
        return JSONResponse({"code": 503, "message": "Captcha unavailable"}, status_code=503)
    headers = {"X-Captcha-Id": captcha_id, "Cache-Control": "no-store"}
    return Response(content=image_bytes, media_type="image/png", headers=headers)


@router.put("/auth/change-password")
async def change_password(request: Request, authorization: str = Header(default="")):
    """修改当前账户密码。"""
    account = authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    old_password = str_field(body, "oldPassword", "old_password")
    new_password = str_field(body, "newPassword", "new_password")
    if not old_password or not new_password:
        return err(400, "oldPassword and newPassword are required", 400)
    if len(new_password) < 6:
        return err(400, "newPassword must be at least 6 characters", 400)
    current_hash = account.get("password_hash")
    if not current_hash:
        return err(4002, "Password is not set; use SMS login", 400)
    if not _verify_password(old_password, current_hash):
        return err(4003, "Incorrect old password", 400)
    new_hash = _hash_password(new_password)
    with connect() as conn:
        conn.execute("UPDATE v2_account SET password_hash=? WHERE id=?", (new_hash, account["id"]))
        conn.commit()
    return {"accountId": account["id"], "updatedAt": now()}
