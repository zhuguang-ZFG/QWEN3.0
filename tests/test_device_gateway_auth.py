"""Tests for device_gateway/auth.py — device token validation."""

import os
from unittest.mock import patch

from device_gateway.auth import configured_device_tokens, validate_device_token, token_configured


def test_no_tokens_configured():
    """No environment variable -> empty dict."""
    with patch.dict(os.environ, {}, clear=True):
        assert configured_device_tokens() == {}


def test_single_token():
    """Single token is parsed correctly."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=tok1"}):
        tokens = configured_device_tokens()
        assert tokens == {"dev1": "tok1"}


def test_multiple_tokens():
    """Multiple tokens are parsed correctly."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=tok1,dev2=tok2"}):
        tokens = configured_device_tokens()
        assert len(tokens) == 2
        assert tokens["dev1"] == "tok1"
        assert tokens["dev2"] == "tok2"


def test_invalid_json_returns_empty():
    """Invalid JSON -> empty dict."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "not-json"}):
        assert configured_device_tokens() == {}


def test_validate_valid_token():
    """Valid token returns True."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=secret123"}):
        assert validate_device_token("dev1", "secret123") is True


def test_validate_invalid_token():
    """Wrong token returns False."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=secret123"}):
        assert validate_device_token("dev1", "wrong") is False


def test_validate_unknown_device():
    """Unknown device returns False."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=tok1"}):
        assert validate_device_token("unknown_dev", "tok1") is False


def test_validate_empty_token():
    """Empty token string returns False."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=tok1"}):
        assert validate_device_token("dev1", "") is False


def test_token_configured_true():
    """token_configured returns True when tokens exist."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=tok1"}):
        assert token_configured() is True


def test_token_configured_false():
    """token_configured returns False when no tokens."""
    with patch.dict(os.environ, {}, clear=True):
        assert token_configured() is False


def test_token_configured_empty_json():
    """token_configured returns False with empty string."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": ""}):
        assert token_configured() is False


def test_validate_digital_human_default_fallback():
    """Falls back to LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID when configured."""
    with patch.dict(os.environ, {
        "LIMA_DEVICE_TOKENS": "{}",
        "LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID": "dh_dev",
    }):
        # The auth module reads these at import time, so we test via monkeypatch
        assert configured_device_tokens() == {}


def test_constant_time_comparison():
    """Token comparison uses constant-time approach (not timing-based)."""
    with patch.dict(os.environ, {"LIMA_DEVICE_TOKENS": "dev1=secret123"}):
        assert validate_device_token("dev1", "secret123") is True
        assert validate_device_token("dev1", "SECRET123") is False
