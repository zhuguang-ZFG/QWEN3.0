import asyncio

import pytest
from fastapi import HTTPException

import access_guard
import routes.admin as admin_routes


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


def test_private_api_key_accepts_bearer_or_raw_key(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEYS", "private-key")
    monkeypatch.delenv("LIMA_API_KEY", raising=False)

    assert access_guard.require_private_api_key("Bearer private-key") is None
    assert access_guard.require_private_api_key("private-key") is None


def test_private_api_key_fails_closed_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)

    with pytest.raises(HTTPException) as exc:
        access_guard.require_private_api_key("Bearer anything")

    assert exc.value.status_code == 503


def test_admin_auth_fails_closed_without_configured_token(monkeypatch):
    monkeypatch.setattr(admin_routes, "_ADMIN_TOKEN", "")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(admin_routes._verify_admin(""))

    assert exc.value.status_code == 503
