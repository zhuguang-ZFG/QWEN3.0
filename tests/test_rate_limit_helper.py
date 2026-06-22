"""Tests for routes/rate_limit_helper — route-level rate-limiting helpers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import routes.rate_limit_helper as rlh


def test_check_ip_limit_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_RATE_LIMIT_DISABLE", "1")
    app = FastAPI()

    @app.get("/test")
    async def test_route(request: Request):
        result = rlh.check_ip_limit(request, "test:scope", 5)
        assert result is None
        return JSONResponse({"ok": True})

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200


def test_check_key_limit_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_RATE_LIMIT_DISABLE", "1")
    result = rlh.check_key_limit("test:key", 5)
    assert result is None


def test_check_ip_limit_blocks_after_limit_exceeded(monkeypatch):
    import rate_limiter

    rate_limiter.reset()
    app = FastAPI()

    @app.get("/test")
    async def test_route(request: Request):
        return rlh.check_ip_limit(request, "test:block", 2) or JSONResponse({"ok": True})

    client = TestClient(app)
    assert client.get("/test").status_code == 200
    assert client.get("/test").status_code == 200
    blocked = client.get("/test")
    assert blocked.status_code == 429
    assert "rate_limit_error" in blocked.json()["error"]["type"]


def test_check_key_limit_blocks_after_limit_exceeded(monkeypatch):
    import rate_limiter

    rate_limiter.reset()
    assert rlh.check_key_limit("test:key:block", 2) is None
    assert rlh.check_key_limit("test:key:block", 2) is None
    blocked = rlh.check_key_limit("test:key:block", 2)
    assert blocked is not None
    assert blocked.status_code == 429
