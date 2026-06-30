"""Integration tests for access_guard dynamic client key support."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import access_guard
import client_keys


def _make_app():
    app = FastAPI()

    @app.get("/allowed")
    @app.get("/blocked")
    def protected(_=Depends(access_guard.require_private_api_key)):
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch, tmp_path):
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    monkeypatch.setattr(
        access_guard,
        "_API_KEYS",
        set(),
    )
    db_path = tmp_path / "client_keys.db"
    client_keys.reset_for_tests(str(db_path))
    yield


def _create_key(label: str, allowed_urls: list[str] | None = None):
    if allowed_urls is None:
        allowed_urls = ["*"]
    return client_keys.storage().create(label, allowed_urls=allowed_urls)


def test_dynamic_keys_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LIMA_CLIENT_KEYS_ENABLED", raising=False)
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        False,
    )
    key = _create_key("test")
    with pytest.raises(Exception):
        access_guard.require_private_api_key(f"Bearer {key.key_value}")


def test_dynamic_key_enabled_no_keys_returns_503(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    with pytest.raises(Exception) as exc:
        access_guard.require_private_api_key("")
    assert exc.value.status_code == 503


def test_dynamic_key_authenticates_with_valid_token(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    key = _create_key("test")
    assert access_guard.require_private_api_key(f"Bearer {key.key_value}") is None


def test_dynamic_key_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    _create_key("test")
    with pytest.raises(Exception) as exc:
        access_guard.require_private_api_key("Bearer wrong-token")
    assert exc.value.status_code == 401


def test_disabled_key_returns_403(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    key = _create_key("test")
    client_keys.storage().update(key.key_id, {"enabled": False})
    with pytest.raises(Exception) as exc:
        access_guard.require_private_api_key(f"Bearer {key.key_value}")
    assert exc.value.status_code == 403


def test_url_allowlist_enforced(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    key = _create_key("url-test", allowed_urls=["/allowed"])
    app = _make_app()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {key.key_value}"}
    assert client.get("/allowed", headers=headers).status_code == 200
    assert client.get("/blocked", headers=headers).status_code == 403


def test_quota_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(
        access_guard.SECURITY,
        "client_keys_enabled",
        True,
    )
    key = _create_key("quota-test", allowed_urls=["*"])
    client_keys.storage().update(key.key_id, {"quota_daily": 1})
    access_guard.require_private_api_key(f"Bearer {key.key_value}")
    with pytest.raises(Exception) as exc:
        access_guard.require_private_api_key(f"Bearer {key.key_value}")
    assert exc.value.status_code == 429
