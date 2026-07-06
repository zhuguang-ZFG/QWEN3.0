"""dlc_api body size 上限中间件（findings.md:584 — 应用层兜底，不只靠 nginx）。

缺口：server_dlc.py 无任何中间件，请求体大小完全依赖 nginx client_max_body_size
兜底。若直连 :8081（绕过 nginx，如内网/调试/nginx 配置漂移）则无上限，
超大 body 可撑爆内存。补一个最小 ASGI 中间件按 Content-Length 快速拒绝（413）。

RED until add_body_size_limit exists.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dlc_api.middleware import add_body_size_limit


def _app(max_bytes: int) -> FastAPI:
    app = FastAPI()
    add_body_size_limit(app, max_bytes=max_bytes)

    @app.post("/echo")
    async def _echo(payload: dict) -> dict:
        return {"ok": True}

    return app


def test_oversized_body_rejected_413() -> None:
    """Content-Length 超阈值应快速返回 413，不进入路由处理。"""
    client = TestClient(_app(max_bytes=100))
    resp = client.post("/echo", content=b"x" * 500, headers={"content-type": "application/json"})
    assert resp.status_code == 413


def test_normal_body_passes() -> None:
    """阈值内的正常请求正常处理。"""
    client = TestClient(_app(max_bytes=10_000))
    resp = client.post("/echo", json={"a": 1})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_server_dlc_has_body_limit() -> None:
    """生产入口 server_dlc:app 必须挂了 body size 中间件。"""
    import server_dlc

    # 中间件通过 user_middleware 注册，检查类名存在。
    names = [m.cls.__name__ for m in server_dlc.app.user_middleware]
    assert "BodySizeLimitMiddleware" in names, f"server_dlc 未挂 body limit 中间件: {names}"
