"""Tests for session_memory/redact.py — memory secret/PII redaction (P2-8)."""

from __future__ import annotations

import pytest

from session_memory.redact import (
    has_secret,
    redact_text,
    sanitize_for_display,
    sanitize_for_memory,
)


@pytest.mark.parametrize(
    "text",
    [
        "my key is sk-abcdefghijklmnopqrstuvwxyz123456",
        "token ghp_1234567890123456789012345678901234567890",
        "xai-123456789012345678901234567890",
        "access AKIA1234567890123456",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def",
        "api_key:supersecretvalue12345678",
        "https://user:pass@example.com/path",
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
    ],
)
def test_has_secret_detects_patterns(text: str):
    assert has_secret(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hello world",
        "the quick brown fox",
        "key=short",
    ],
)
def test_has_secret_negative(text: str):
    assert has_secret(text) is False


def test_redact_text_api_key():
    text = "key is sk-abcdefghijklmnopqrstuvwxyz123456 end"
    assert "[REDACTED]" in redact_text(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redact_text(text)


def test_redact_text_url_credentials():
    text = "repo https://user:pass@example.com/path ok"
    assert "[REDACTED_URL]" in redact_text(text)
    assert "https://user:pass@example.com/path" not in redact_text(text)


def test_redact_text_ssh_key():
    text = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
    assert "[REDACTED_KEY]" in redact_text(text)
    assert "BEGIN OPENSSH PRIVATE KEY" not in redact_text(text)


def test_sanitize_for_memory_empty():
    assert sanitize_for_memory("") is None
    assert sanitize_for_memory("   ") is None


def test_sanitize_for_memory_rejects_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
    assert sanitize_for_memory(text) is None


def test_sanitize_for_memory_redacts_secrets(caplog):
    text = "key is sk-abcdefghijklmnopqrstuvwxyz123456"
    cleaned = sanitize_for_memory(text)
    assert cleaned is not None
    assert "[REDACTED]" in cleaned


def test_sanitize_for_display_redacts_but_does_not_reject():
    text = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
    displayed = sanitize_for_display(text)
    assert "[REDACTED_KEY]" in displayed
    assert "BEGIN RSA PRIVATE KEY" not in displayed
