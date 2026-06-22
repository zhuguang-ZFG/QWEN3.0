"""LiMa admin routes: session UI + API wiring (CQ-014 slice 11)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, JSONResponse

from routes.admin_api import router as admin_api_router
from routes.admin_api_extra import router as admin_api_extra_router
from routes.admin_auth import (
    SESSION_COOKIE,
    admin_session_value,
    get_admin_token,
    is_valid_admin_session,
)
from routes.admin_state import inject_state
from access_guard import constant_time_equals
from routes.admin_ui import render_admin_dashboard
from routes.rate_limit_helper import check_ip_limit

router = APIRouter(prefix="/admin")
router.include_router(admin_api_router)
router.include_router(admin_api_extra_router)

__all__ = ["router", "inject_state"]

_ADMIN_LOGIN_MAX_PER_MIN = int(os.environ.get("LIMA_ADMIN_LOGIN_PER_MIN", "10"))


@router.get("", response_class=HTMLResponse)
async def admin_page(lima_admin_session: str = Cookie(default="")):
    if not get_admin_token():
        raise HTTPException(503, "LIMA_ADMIN_TOKEN not configured")
    if not is_valid_admin_session(lima_admin_session):
        return HTMLResponse(
            "<h2>Admin Login</h2>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    return HTMLResponse(render_admin_dashboard())


@router.post("/login")
async def admin_login(request: Request):
    rate_limit_response = check_ip_limit(request, "admin:login", _ADMIN_LOGIN_MAX_PER_MIN)
    if rate_limit_response is not None:
        return rate_limit_response
    form = await request.form()
    token = form.get("token", "")
    expected = get_admin_token()
    if not expected or not constant_time_equals(str(token), expected):
        return HTMLResponse(
            "<h2>Admin Login</h2><p style='color:red'>Token 错误</p>"
            '<form method="post" action="/admin/login">'
            '<input name="token" placeholder="Admin Token" type="password">'
            '<button type="submit">Login</button></form>',
            status_code=401,
        )
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        admin_session_value(),
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,
    )
    return response


@router.get("/logout")
async def admin_logout():
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(SESSION_COOKIE, secure=True, samesite="strict")
    return response
