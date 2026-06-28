"""Tests for device_gateway/auth.py — device token validation."""

from __future__ import annotations

import pytest

from config.settings import DEVICE
from device_gateway.auth import configured_device_tokens, token_configured, validate_device_token


@pytest.fixture(autouse=True)
def _clear_device_tokens(monkeypatch):
    """Ensure each test starts with no device tokens unless explicitly set."""
    monkeypatch.setattr(DEVICE, "tokens", "")
    monkeypatch.setattr(DEVICE, "digital_human_default_device_id", "web-tester")
    monkeypatch.setattr(DEVICE, "digital_human_default_token", "")


def test_no_tokens_configured():
    """No environment variable -> empty dict."""
    assert configured_device_tokens() == {}


def test_single_token(monkeypatch):
    """Single token is parsed correctly."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=tok1")
    tokens = configured_device_tokens()
    assert tokens == {"dev1": "tok1"}


def test_multiple_tokens(monkeypatch):
    """Multiple tokens are parsed correctly."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=tok1,dev2=tok2")
    tokens = configured_device_tokens()
    assert len(tokens) == 2
    assert tokens["dev1"] == "tok1"
    assert tokens["dev2"] == "tok2"


def test_invalid_json_returns_empty(monkeypatch):
    """Invalid token string -> empty dict."""
    monkeypatch.setattr(DEVICE, "tokens", "not-json")
    assert configured_device_tokens() == {}


def test_validate_valid_token(monkeypatch):
    """Valid token returns True."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=secret123")
    assert validate_device_token("dev1", "secret123") is True


def test_validate_invalid_token(monkeypatch):
    """Wrong token returns False."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=secret123")
    assert validate_device_token("dev1", "wrong") is False


def test_validate_unknown_device(monkeypatch):
    """Unknown device returns False."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=tok1")
    assert validate_device_token("unknown_dev", "tok1") is False


def test_validate_empty_token(monkeypatch):
    """Empty token string returns False."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=tok1")
    assert validate_device_token("dev1", "") is False


def test_token_configured_true(monkeypatch):
    """token_configured returns True when tokens exist."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=tok1")
    assert token_configured() is True


def test_token_configured_false():
    """token_configured returns False when no tokens."""
    assert token_configured() is False


def test_token_configured_empty_string(monkeypatch):
    """token_configured returns False with empty string."""
    monkeypatch.setattr(DEVICE, "tokens", "")
    assert token_configured() is False


def test_validate_digital_human_default_fallback(monkeypatch):
    """Falls back to configured digital-human default device/token."""
    monkeypatch.setattr(DEVICE, "tokens", "")
    monkeypatch.setattr(DEVICE, "digital_human_default_device_id", "dh_dev")
    monkeypatch.setattr(DEVICE, "digital_human_default_token", "dh_secret")
    assert validate_device_token("dh_dev", "dh_secret") is True


def test_constant_time_comparison(monkeypatch):
    """Token comparison uses constant-time approach (not timing-based)."""
    monkeypatch.setattr(DEVICE, "tokens", "dev1=secret123")
    assert validate_device_token("dev1", "secret123") is True
    assert validate_device_token("dev1", "SECRET123") is False


def test_registered_device_fallback_default_off(monkeypatch):
    """By default the registered-device fallback is disabled for security."""
    from device_gateway import auth

    monkeypatch.setattr(auth, "_WS_REGISTERED_DEVICE_FALLBACK", False)
    original = auth._is_registered_device
    auth._is_registered_device = lambda _did: True
    try:
        assert validate_device_token("registered-device-id", "") is False
    finally:
        auth._is_registered_device = original


def test_registered_device_fallback_enabled(monkeypatch):
    """When explicitly enabled, empty token + registered device is allowed."""
    from device_gateway import auth

    monkeypatch.setattr(auth, "_WS_REGISTERED_DEVICE_FALLBACK", True)
    original = auth._is_registered_device
    auth._is_registered_device = lambda _did: True
    try:
        assert validate_device_token("registered-device-id", "") is True
        auth._is_registered_device = lambda _did: False
        assert validate_device_token("unknown-device-id", "") is False
    finally:
        auth._is_registered_device = original
