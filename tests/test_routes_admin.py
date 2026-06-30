"""Tests for routes/admin.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin
from routes import admin_auth


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    app = FastAPI()
    app.include_router(admin.router)
    return TestClient(app)


def test_admin_page_no_token_returns_503(client, monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "")
    response = client.get("/admin")
    assert response.status_code == 503


def test_admin_page_invalid_cookie_returns_login_form(client):
    client.cookies.set(admin_auth.SESSION_COOKIE, "invalid")
    response = client.get("/admin")
    assert response.status_code == 401
    assert "Admin Login" in response.text


def test_admin_page_valid_cookie_returns_dashboard(client):
    with patch.object(admin, "render_admin_dashboard", return_value="<h1>Dashboard</h1>"):
        cookie = admin_auth.admin_session_value()
        client.cookies.set(admin_auth.SESSION_COOKIE, cookie)
        response = client.get("/admin")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_admin_login_wrong_token_returns_error(client):
    response = client.post("/admin/login", data={"token": "wrong"})
    assert response.status_code == 401
    assert "Token 错误" in response.text


def test_admin_login_correct_token_sets_cookie(client):
    response = client.post("/admin/login", data={"token": "admin-token"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert admin_auth.SESSION_COOKIE in response.cookies


def test_admin_logout_clears_cookie(client):
    response = client.get("/admin/logout", follow_redirects=False)
    assert response.status_code == 303
    set_cookie = response.headers.get("set-cookie", "")
    assert admin_auth.SESSION_COOKIE in set_cookie
    assert "Max-Age=0" in set_cookie or "expires" in set_cookie.lower()
