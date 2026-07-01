"""LiMa native device app auth routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, Request

from config.env import (
    wechat_dev_login_enabled,
    wechat_miniapp_appid,
    wechat_miniapp_secret,
)
from fastapi.responses import JSONResponse

from device_logic.auth import (
    _hash_password,
    _login_response,
    _verify_password,
    account_payload,
    authorize,
)
from device_logic.auth_rate import allow_device_auth
from device_logic.db import connect
from device_logic.http import err, new_id, now, read_body, str_field
from device_logic.wechat_gateway import WechatLoginError, WechatMiniappGateway
from routes import device_app_auth_email, device_app_auth_keys
from routes.request_tracking import client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device/v1/app", tags=["device-app-auth"])
router.include_router(device_app_auth_email.router)
router.include_router(device_app_auth_keys.router)


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


async def _login_by_wechat(body: dict) -> dict | JSONResponse:
    """Handle WeChat-code login path.

    Production: call WeChat jscode2session with configured appid/secret.
    Dev: if LIMA_XIAOZHI_WECHAT_DEV_LOGIN=1, treat code as openid for local tests.
    """
    code = str_field(body, "code", "smsCode")
    appid = wechat_miniapp_appid()
    secret = wechat_miniapp_secret()
    if appid and secret:
        try:
            gateway = WechatMiniappGateway(appid, secret)
            session = await gateway.jscode2session(code)
            openid = session["openid"]
        except WechatLoginError as exc:
            logger.warning("WeChat login failed for appid=%s: %s", appid, exc)
            return err(401, f"WeChat login failed: {exc}", 401)
    elif wechat_dev_login_enabled():
        openid = f"wx:{code}"
    else:
        return err(503, "WeChat login is not configured", 503)
    row = _find_or_create_wechat_account(openid, body.get("nickname"))
    return _login_response(row)


@router.post("/auth/login")
async def login(request: Request):
    """WeChat one-tap login (mini-program) or email login (chat-web /官网).

    手机号+短信登录已于 2026-07-02 弃用移除（slimdown P2-16）。
    小程序走微信一键登录；chat-web 与官网走 /auth/login-email（device_app_auth_email.py）。
    """
    if not allow_device_auth("login", client_ip(request)):
        return err(429, "Too many login attempts", 429)
    body = await read_body(request)
    if isinstance(body, JSONResponse):
        return body
    code = str_field(body, "code", "smsCode")
    if not code:
        return err(400, "code is required", 400)
    data = await _login_by_wechat(body)
    if isinstance(data, JSONResponse):
        return data
    return data


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
        return err(4002, "Password is not set", 400)
    if not _verify_password(old_password, current_hash):
        return err(4003, "Incorrect old password", 400)
    new_hash = _hash_password(new_password)
    with connect() as conn:
        conn.execute("UPDATE v2_account SET password_hash=? WHERE id=?", (new_hash, account["id"]))
        conn.commit()
    return {"accountId": account["id"], "updatedAt": now()}
