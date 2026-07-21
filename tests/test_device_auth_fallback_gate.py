"""Production gate for empty-token device WS fallback (B1)."""

from __future__ import annotations

import pytest

from device_gateway import auth as auth_mod


def test_assert_device_auth_safe_ok_when_fallback_off(monkeypatch):
    monkeypatch.setattr(auth_mod, "_WS_REGISTERED_DEVICE_FALLBACK", False)
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    auth_mod.assert_device_auth_safe_for_runtime()


def test_assert_device_auth_safe_blocks_production_fallback(monkeypatch):
    monkeypatch.setattr(auth_mod, "_WS_REGISTERED_DEVICE_FALLBACK", True)
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.delenv("LIMA_WS_FALLBACK_ALLOW_PRODUCTION", raising=False)
    with pytest.raises(RuntimeError, match="forbidden"):
        auth_mod.assert_device_auth_safe_for_runtime()


def test_assert_device_auth_safe_allows_explicit_production_escape(monkeypatch):
    monkeypatch.setattr(auth_mod, "_WS_REGISTERED_DEVICE_FALLBACK", True)
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    monkeypatch.setenv("LIMA_WS_FALLBACK_ALLOW_PRODUCTION", "1")
    auth_mod.assert_device_auth_safe_for_runtime()
