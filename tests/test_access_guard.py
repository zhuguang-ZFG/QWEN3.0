import asyncio
import json

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

import access_guard
import routes.admin as admin_routes
import routes.admin_auth as admin_auth
import routes.admin_client_keys as admin_client_keys


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


def _make_protected_app():
    app = FastAPI()

    @app.get("/allowed")
    @app.get("/blocked")
    def protected(_=Depends(access_guard.require_private_api_key)):
        return {"ok": True}

    return app


def test_dynamic_client_key_disabled_by_default(monkeypatch, tmp_path):
    """Without LIMA_CLIENT_KEYS_ENABLED, dynamic keys are ignored."""
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    monkeypatch.delenv("LIMA_CLIENT_KEYS_ENABLED", raising=False)

    keys_path = tmp_path / "client_keys.json"
    keys_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "ck-test",
                        "key_value": "lima-test-token-1234",
                        "label": "test",
                        "enabled": True,
                        "created_at": 0,
                        "allowed_urls": ["*"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_client_keys, "_KEYS_PATH", keys_path)

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("Bearer lima-test-token-1234")
    assert exc.value.status_code == 503


def test_dynamic_client_key_returns_401_when_configured(monkeypatch, tmp_path):
    """With LIMA_CLIENT_KEYS_ENABLED=1 and keys on disk, missing/invalid tokens return 401."""
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    monkeypatch.setenv("LIMA_CLIENT_KEYS_ENABLED", "1")

    keys_path = tmp_path / "client_keys.json"
    keys_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "ck-test",
                        "key_value": "lima-test-token-1234",
                        "label": "test",
                        "enabled": True,
                        "created_at": 0,
                        "allowed_urls": ["*"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_client_keys, "_KEYS_PATH", keys_path)

    # Missing token
    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("")
    assert exc.value.status_code == 401

    # Invalid token
    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("Bearer wrong-token")
    assert exc.value.status_code == 401

    # Valid token
    assert access_guard.require_private_api_key("Bearer lima-test-token-1234") is None


def test_dynamic_client_key_url_allowlist_enforced(monkeypatch, tmp_path):
    """URL allowlist is enforced when the dependency is used on a route with Request."""
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    monkeypatch.setenv("LIMA_CLIENT_KEYS_ENABLED", "1")

    keys_path = tmp_path / "client_keys.json"
    keys_path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "ck-test",
                        "key_value": "lima-test-token-1234",
                        "label": "test",
                        "enabled": True,
                        "created_at": 0,
                        "allowed_urls": ["/allowed"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(admin_client_keys, "_KEYS_PATH", keys_path)

    app = _make_protected_app()
    client = TestClient(app)

    headers = {"Authorization": "Bearer lima-test-token-1234"}
    assert client.get("/allowed", headers=headers).status_code == 200
    assert client.get("/blocked", headers=headers).status_code == 403
