"""LiMa admin routes: session UI + API wiring (CQ-014 slice 11)."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from access_guard import constant_time_equals
from routes.admin_api import router as admin_api_router
from routes.admin_auth import (
    SESSION_COOKIE,
    admin_session_value,
    get_admin_token,
    is_valid_admin_session,
)
from routes.admin_backends_crud import router as admin_backends_router
from routes.admin_state import inject_state
from routes.admin_ui import render_admin_dashboard, render_admin_login

router = APIRouter(prefix="/admin")
router.include_router(admin_api_router)
router.include_router(admin_backends_router)
_log = logging.getLogger(__name__)

# ── Login Rate Limiting ──────────────────────────────────────────────────────
# NOTE: In-memory rate limiter. In multi-process deployments (gunicorn,
# uvicorn --workers), each worker maintains its own counter. For production
# hardening, migrate to Redis or shared database.
# 防止暴力破解：每 IP 5 次失败/15 分钟
# ─────────────────────────────────────────────────────────────────────────────
_LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_LOGIN_RATE_LIMIT = 5  # 最大失败次数
_LOGIN_RATE_WINDOW = 900  # 15 分钟（秒）


def _check_login_rate_limit(client_ip: str) -> bool:
    """检查 IP 是否超过登录失败速率限制。返回 True 如果允许登录。"""
    now = time.time()
    # 清理过期记录
    _LOGIN_ATTEMPTS[client_ip] = [
        t for t in _LOGIN_ATTEMPTS[client_ip]
        if now - t < _LOGIN_RATE_WINDOW
    ]
    # 检查是否超过限制
    if len(_LOGIN_ATTEMPTS[client_ip]) >= _LOGIN_RATE_LIMIT:
        return False
    return True


def _record_login_failure(client_ip: str) -> None:
    """记录登录失败。"""
    _LOGIN_ATTEMPTS[client_ip].append(time.time())

__all__ = ["router", "inject_state"]


@router.get("", response_class=HTMLResponse)
async def admin_page(lima_admin_session: str = Cookie(default="")):
    if not get_admin_token():
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    if not is_valid_admin_session(lima_admin_session):
        return HTMLResponse(render_admin_login(), status_code=401)
    return HTMLResponse(render_admin_dashboard())


@router.post("/login")
async def admin_login(request: Request):
    # Rate limit check
    client_ip = request.client.host if request.client else "unknown"
    if not _check_login_rate_limit(client_ip):
        _log.warning("admin: login rate limit exceeded for IP %s", client_ip)
        return HTMLResponse(
            render_admin_login("Too many failed attempts. Please try again later."),
            status_code=429,
        )
    
    form = await request.form()
    token = form.get("token", "")
    expected = get_admin_token()
    if not expected or not constant_time_equals(str(token), expected):
        _record_login_failure(client_ip)
        _log.warning("admin: login failed for IP %s", client_ip)
        return HTMLResponse(render_admin_login("Token error"), status_code=401)
    
    # Success - clear failure history
    if client_ip in _LOGIN_ATTEMPTS:
        del _LOGIN_ATTEMPTS[client_ip]
    
    # secure=True 在 localhost 测试时会导致 cookie 被浏览器拒绝
    # 生产环境应始终为 True
    # 使用环境变量或 X-Forwarded-Proto header 判断，支持反向代理场景
    is_production = (
        os.getenv("LIMA_PRODUCTION", "").lower() in ("1", "true", "yes")
        or request.headers.get("X-Forwarded-Proto", "") == "https"
        or not (request.url.hostname or "").startswith(("localhost", "127.0.0.1"))
    )
    
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        admin_session_value(),
        httponly=True,
        secure=is_production,  # 生产环境强制 secure
        samesite="strict",
        max_age=86400,
    )
    return response


@router.get("/logout")
async def admin_logout(request: Request):
    # secure flag must match login
    is_production = (
        os.getenv("LIMA_PRODUCTION", "").lower() in ("1", "true", "yes")
        or request.headers.get("X-Forwarded-Proto", "") == "https"
        or not (request.url.hostname or "").startswith(("localhost", "127.0.0.1"))
    )
    
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(SESSION_COOKIE, secure=is_production, samesite="strict")
    return response
