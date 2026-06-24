"""Tests for routes/admin_v1_auth.py — admin email/password JWT login."""

import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_v1_auth import router as admin_v1_auth_router
from routes import admin_auth


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-jwt-secret-for-admin-v1-auth")
    # Reload config so the new env value is picked up by settings.SECURITY.jwt_secret
    import config.settings as settings_mod

    if hasattr(settings_mod, "_SETTINGS"):
        settings_mod._SETTINGS = None


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(admin_v1_auth_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify


def _unique_email() -> str:
    return f"admin-{uuid.uuid4().hex[:8]}@example.com"


def _bootstrap_user(client: TestClient, email: str = "", password: str = "password123") -> tuple[dict, str]:
    email = email or _unique_email()
    response = client.post(
        "/admin/v1/auth/bootstrap",
        json={"email": email, "password": password, "nickname": "Admin"},
    )
    assert response.status_code == 200, response.text
    return response.json()["user"], email


class TestAdminV1Auth:
    def test_bootstrap_and_login(self):
        client = TestClient(app)
        user, email = _bootstrap_user(client)
        assert user["email"] == email
        assert user["role"] == "admin"

        response = client.post(
            "/admin/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == email

    def test_login_invalid_password(self):
        client = TestClient(app)
        _, email = _bootstrap_user(client)
        response = client.post(
            "/admin/v1/auth/login",
            json={"email": email, "password": "wrong"},
        )
        assert response.status_code == 401

    def test_me_endpoint(self):
        client = TestClient(app)
        _, email = _bootstrap_user(client)
        login = client.post(
            "/admin/v1/auth/login",
            json={"email": email, "password": "password123"},
        )
        token = login.json()["token"]
        response = client.get("/admin/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["email"] == email
        assert data["role"] == "admin"

    def test_me_missing_token(self):
        client = TestClient(app)
        response = client.get("/admin/v1/auth/me")
        assert response.status_code == 401
