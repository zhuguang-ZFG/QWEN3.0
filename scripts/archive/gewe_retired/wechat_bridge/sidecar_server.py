"""LiMa WeChat sidecar: Gewechat callback + login QR page."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from wechat_bridge.callback_handler import handle_callback
from wechat_bridge.gewechat_client import GewechatClient

app = FastAPI(title="LiMa WeChat Sidecar")

_state: dict = {"qr_html": "", "app_id": "", "gewe_token": ""}


def _gewe() -> GewechatClient:
    base = os.environ.get("GEWECHAT_BASE_URL", "http://127.0.0.1:2531/v2/api")
    token = _state.get("gewe_token") or os.environ.get("GEWECHAT_TOKEN", "")
    return GewechatClient(base, token)


@app.get("/health")
def health():
    return {"ok": True, "service": "lima-wechat-sidecar"}


@app.get("/login-qr", response_class=HTMLResponse)
def login_qr_page():
    html = _state.get("qr_html") or "<p>二维码未生成。请运行 scripts/wechat_joint_debug.py refresh-qr</p>"
    return HTMLResponse(html)


@app.post("/v2/api/callback/collect")
async def gewechat_callback(request: Request):
    payload = await request.json()
    result = handle_callback(
        payload,
        gewe=_gewe(),
        lima_base=os.environ.get("LIMA_CHANNEL_BASE_URL", "http://127.0.0.1:8080"),
        lima_token=os.environ.get("LIMA_WECHAT_SIDECAR_TOKEN", ""),
    )
    return JSONResponse(result)


def set_qr_html(html: str, *, app_id: str = "", gewe_token: str = "") -> None:
    _state["qr_html"] = html
    if app_id:
        _state["app_id"] = app_id
    if gewe_token:
        _state["gewe_token"] = gewe_token
