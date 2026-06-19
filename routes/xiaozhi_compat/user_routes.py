"""User and authentication routes for XiaoZhi v1 compatibility API."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response

from .shared import (
    authorize,
    ok,
    err,
    read_body,
    connect,
    now,
    new_id,
    str_field,
    account_payload,
    make_token,
    _hash_password,
    _verify_password,
    create_captcha,
    generate_captcha_image,
    verify_captcha,
)
from .sms import (
    captcha_required,
    extract_captcha_fields,
    login_code_error,
    sms_verification_payload,
    validate_login_code,
)

router = APIRouter()


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


def _login_or_register(body: dict) -> dict | JSONResponse:
    """Shared phone+code login / auto-register logic."""
    phone = str_field(body, "phone", "mobile")
    code = str_field(body, "code", "smsCode")
    if not phone or not code:
        return err(400, "phone and code are required", 400)
    config_error = login_code_error()
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
    return login_response(row)


@router.post("/login")
async def login(request: Request) -> JSONResponse:
    """手机号+验证码登录，自动注册新用户。"""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    data = _login_or_register(body)
    if isinstance(data, JSONResponse):
        return data
    return ok(data)


@router.post("/auth/login")
async def login_alias(request: Request) -> JSONResponse:
    """OpenAPI-compatible alias for /login."""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    data = _login_or_register(body)
    if isinstance(data, JSONResponse):
        return data
    return ok(data)


@router.post("/auth/register")
async def register(request: Request) -> JSONResponse:
    """Register a phone account with the Phase 0 SMS verification code."""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    data = _login_or_register(body)
    if isinstance(data, JSONResponse):
        return data
    return ok(data)


@router.get("/auth/captcha")
async def get_captcha(uuid: str | None = None) -> Response:
    """Return a PNG captcha image and its captchaId."""
    captcha_id, code = create_captcha()
    image_bytes = generate_captcha_image(code)
    if image_bytes is None:
        return JSONResponse(
            {"code": 503, "message": "Captcha image generation is unavailable"},
            status_code=503,
        )
    headers = {
        "X-Captcha-Id": captcha_id,
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    # If caller supplied a uuid query param, we still generate a fresh id; include both for compatibility.
    if uuid:
        headers["X-Requested-Uuid"] = uuid
    return Response(content=image_bytes, media_type="image/png", headers=headers)


@router.post("/auth/sms-verification")
async def sms_verification(request: Request) -> JSONResponse:
    """Return the Phase 0 mock SMS code."""
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = str_field(body, "phone", "mobile")
    if not phone:
        return err(400, "phone is required", 400)
    config_error = login_code_error()
    if config_error:
        return config_error

    captcha_id, captcha_code = extract_captcha_fields(body)
    if captcha_required() or captcha_id or captcha_code:
        captcha_error = verify_captcha(captcha_id, captcha_code)
        if captcha_error is not None:
            return captcha_error

    return ok(sms_verification_payload(phone))


@router.put("/auth/change-password")
async def change_password(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Change the current account's password (only useful when password login is enabled)."""
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
        return err(4002, "Password is not set for this account; use SMS login", 400)
    if not _verify_password(old_password, current_hash):
        return err(4003, "Incorrect old password", 400)

    new_hash = _hash_password(new_password)
    if new_hash is None:
        return err(503, "Password hashing is unavailable", 503)
    with connect() as conn:
        conn.execute("UPDATE v2_account SET password_hash=? WHERE id=?", (new_hash, account["id"]))
        conn.commit()
    return ok({"accountId": account["id"], "updatedAt": now()})


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
                avatar_url=NULL,
                password_hash=NULL
            WHERE id=?
            """,
            (deleted_at, account["id"]),
        )
        conn.commit()
    return ok({"accountId": account["id"], "deletedAt": deleted_at})
