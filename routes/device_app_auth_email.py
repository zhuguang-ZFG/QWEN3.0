"""Email/password auth routes for the device app console."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from device_logic import db as _db
from device_logic.auth import _hash_password, _login_response, _verify_password
from device_logic.auth_email import account_by_email, is_valid_email
from device_logic.auth_rate import allow_device_auth
from device_logic.http import err, new_id, read_body, str_field
from routes.request_tracking import client_ip

router = APIRouter(tags=["device-app-auth"])


@router.post("/auth/register-email")
async def register_email(request: Request):
    if not allow_device_auth("register", client_ip(request)):
        return err(429, "Too many registration attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    email = str_field(body, "email")
    password = str_field(body, "password")
    if not is_valid_email(email):
        return err(400, "A valid email is required", 400)
    if not password or len(password) < 6:
        return err(400, "password must be at least 6 characters", 400)
    if account_by_email(email):
        return err(409, "Email already registered", 409)
    account_id = new_id()
    with _db.connect() as conn:
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
    if not is_valid_email(email):
        return err(400, "A valid email is required", 400)
    if not password:
        return err(400, "password is required", 400)
    row = account_by_email(email)
    if row is None or not _verify_password(password, row["password_hash"]):
        return err(401, "Invalid email or password", 401)
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return data
