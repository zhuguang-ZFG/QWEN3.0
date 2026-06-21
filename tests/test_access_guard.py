import asyncio

import pytest
from fastapi import HTTPException
from fastapi import FastAPI
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


def test_private_api_key_rejects_anonymous_even_when_public_anonymous_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "private-key")
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("")

    assert exc.value.status_code == 401


def test_public_api_key_allows_anonymous_when_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "private-key")
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")
    monkeypatch.delenv("LIMA_RUNTIME_ENV", raising=False)

    assert access_guard.require_public_or_private_api_key("") is None


def test_production_blocks_anonymous_even_when_env_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "private-key")
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")

    assert access_guard.allow_anonymous_access() is False
    status = access_guard.anonymous_access_status()
    assert status["env_enabled"] is True
    assert status["production_blocked"] is True
    assert status["allowed"] is False

    with pytest.raises(HTTPException) as exc:
        access_guard.require_public_or_private_api_key("")
    assert exc.value.status_code == 401


def test_private_api_key_still_validates_explicit_key_when_anonymous_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "private-key")
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")

    assert access_guard.require_private_api_key("Bearer private-key") is None

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("Bearer wrong-key")
    assert exc.value.status_code == 401


def test_private_api_key_anonymous_still_fails_when_no_keys_configured(monkeypatch):
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("")

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


class _DummyWebSocket:
    def __init__(self, headers=None):
        self.headers = headers or {}


@pytest.mark.parametrize(
    "headers,query,expected_token,expected_used_query",
    [
        ({}, "", "", False),
        ({"authorization": "Bearer header-token"}, "", "header-token", False),
        ({}, "Bearer query-token", "query-token", True),
        ({"authorization": "Bearer header-token"}, "Bearer query-token", "header-token", False),
        ({"authorization": "Basic foo"}, "Bearer query-token", "query-token", True),
        ({}, "not-a-bearer", "", False),
        ({}, "   Bearer spaced-token  ", "spaced-token", True),
    ],
)
def test_extract_websocket_token_prefers_header_and_flags_query_param(
    headers, query, expected_token, expected_used_query
):
    ws = _DummyWebSocket(headers)
    token, used_query = access_guard.extract_websocket_token(ws, query)
    assert token == expected_token
    assert used_query == expected_used_query
