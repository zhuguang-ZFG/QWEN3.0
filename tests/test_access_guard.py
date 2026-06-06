import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import access_guard
import routes.admin as admin_routes
import routes.admin_auth as admin_auth


def test_configured_api_keys_accepts_primary_and_list(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "primary")
    monkeypatch.setenv("LIMA_API_KEYS", "alpha, beta ,, gamma")

    assert access_guard.configured_api_keys() == {
        "primary",
        "alpha",
        "beta",
        "gamma",
    }


def test_private_api_key_rejects_missing_authorization(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "private-key")
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("")

    assert exc.value.status_code == 401


def test_private_api_key_requires_bearer_prefix(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEYS", "private-key")
    monkeypatch.delenv("LIMA_API_KEY", raising=False)

    # Bearer prefix is required
    assert access_guard.require_private_api_key("Bearer private-key") is None

    # Raw token without Bearer prefix is rejected
    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("private-key")
    assert exc.value.status_code == 401

    # Malformed Bearer is rejected
    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("bearer private-key")
    assert exc.value.status_code == 401


def test_private_api_key_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("Bearer anything")

    assert exc.value.status_code == 503


def test_admin_auth_fails_closed_without_configured_token(monkeypatch):
    monkeypatch.setattr(admin_auth, "_ADMIN_TOKEN", "")
    monkeypatch.delenv("LIMA_ADMIN_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(admin_auth.verify_admin(""))

    assert exc.value.status_code == 503


def test_admin_page_rejects_query_token_login(monkeypatch):
    monkeypatch.setattr(admin_auth, "_ADMIN_TOKEN", "secret-admin-token")
    monkeypatch.delenv("LIMA_ADMIN_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app, base_url="https://testserver")

    response = client.get("/admin?token=secret-admin-token")

    assert response.status_code == 401


def test_admin_page_does_not_render_admin_token_after_cookie_login(monkeypatch):
    monkeypatch.setattr(admin_auth, "_ADMIN_TOKEN", "secret-admin-token")
    monkeypatch.delenv("LIMA_ADMIN_TOKEN", raising=False)
    app = FastAPI()
    app.include_router(admin_routes.router)
    client = TestClient(app, base_url="https://testserver")

    login = client.post(
        "/admin/login",
        data={"token": "secret-admin-token"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    response = client.get("/admin")

    assert response.status_code == 200
    assert "secret-admin-token" not in response.text
    assert "const _ADMIN_TOKEN" not in response.text
