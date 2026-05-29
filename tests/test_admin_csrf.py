import asyncio
import os
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.admin import router as admin_router
import routes.admin_auth as admin_auth
import routes.admin as admin_routes


def test_csrf_rejects_cross_origin_cookie_request():
    request = type("Req", (), {"url": type("URL", (), {"hostname": "chat.example.com"})()})()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(admin_auth.verify_csrf(
            request,
            authorization="",
            origin="https://evil.example.com",
            referer="",
        ))
    assert exc.value.status_code == 403


def test_csrf_allows_matching_origin():
    request = type("Req", (), {"url": type("URL", (), {"hostname": "chat.example.com"})()})()
    assert asyncio.run(admin_auth.verify_csrf(
        request,
        authorization="",
        origin="https://chat.example.com",
        referer="",
    )) is None


def test_csrf_allows_bearer_authenticated_request():
    request = type("Req", (), {"url": type("URL", (), {"hostname": "chat.example.com"})()})()
    assert asyncio.run(admin_auth.verify_csrf(
        request,
        authorization="Bearer secret-token",
        origin="https://evil.example.com",
        referer="",
    )) is None


def test_admin_login_uses_constant_time_compare(monkeypatch):
    monkeypatch.setattr(admin_auth, "_ADMIN_TOKEN", "secret-admin-token")
    monkeypatch.delenv("LIMA_ADMIN_TOKEN", raising=False)
    calls: list[tuple[str, str]] = []

    def _fake_compare(a: str, b: str) -> bool:
        calls.append((a, b))
        return a == b

    monkeypatch.setattr(admin_routes, "constant_time_equals", _fake_compare)

    app = FastAPI()
    app.include_router(admin_router)
    client = TestClient(app, base_url="https://testserver")
    response = client.post(
        "/admin/login",
        data={"token": "secret-admin-token"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert calls == [("secret-admin-token", "secret-admin-token")]


def test_admin_toggle_backend_requires_csrf_for_cookie_session(monkeypatch):
    monkeypatch.setattr(admin_auth, "_ADMIN_TOKEN", "secret-admin-token")
    monkeypatch.delenv("LIMA_ADMIN_TOKEN", raising=False)

    app = FastAPI()
    app.include_router(admin_router)
    client = TestClient(app, base_url="https://testserver")

    login = client.post(
        "/admin/login",
        data={"token": "secret-admin-token"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    denied = client.post("/admin/api/backends/demo-backend/toggle")
    assert denied.status_code == 403

    allowed = client.post(
        "/admin/api/backends/demo-backend/toggle",
        headers={
            "Origin": "https://testserver",
            "Referer": "https://testserver/admin",
        },
    )
    assert allowed.status_code in (200, 404)
