"""Tests for session_memory/redact.py — secret and PII detection/redaction."""

import pytest

from session_memory.redact import (
    has_secret,
    redact_text,
    sanitize_for_memory,
    sanitize_for_display,
)


class TestHasSecret:
    def test_no_secret(self):
        assert has_secret("hello world") is False

    def test_openai_key(self):
        assert has_secret("sk-" + "a" * 48) is True

    def test_anthropic_key(self):
        assert has_secret("sk-ant-" + "a" * 30) is True

    def test_github_token(self):
        assert has_secret("ghp_" + "a" * 36) is True

    def test_xai_key(self):
        assert has_secret("xai-" + "a" * 24) is True

    def test_aws_key(self):
        assert has_secret("AKIA1234567890123456") is True

    def test_jwt_token(self):
        assert has_secret("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNrxP8bBSK5iMraTxQ") is True

    def test_bearer_token(self):
        assert has_secret("Bearer " + "a" * 30) is True

    def test_keyword_with_value(self):
        assert has_secret("password = supersecretkey12345") is True

    def test_credential_url(self):
        assert has_secret("https://user:pass@example.com") is True

    def test_ssh_key_header(self):
        assert has_secret("-----BEGIN RSA PRIVATE KEY-----") is True

    def test_empty_string(self):
        assert has_secret("") is False


class TestRedactText:
    def test_no_secret_no_change(self):
        assert redact_text("hello world") == "hello world"

    def test_openai_key_redacted(self):
        result = redact_text("key=sk-" + "a" * 48)
        assert "[REDACTED]" in result
        assert "sk-" not in result

    def test_jwt_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNrxP8bBSK5iMraTxQ"
        result = redact_text(f"token={jwt}")
        assert "[REDACTED]" in result

    def test_credential_url_redacted(self):
        result = redact_text("url=https://user:pass@example.com")
        assert "[REDACTED_URL]" in result

    def test_ssh_key_redacted(self):
        result = redact_text("-----BEGIN RSA PRIVATE KEY-----")
        assert "[REDACTED_KEY]" in result

    def test_bearer_token_redacted(self):
        result = redact_text("Authorization: Bearer " + "a" * 30)
        assert "[REDACTED]" in result


class TestSanitizeForMemory:
    def test_empty_returns_none(self):
        assert sanitize_for_memory("") is None
        assert sanitize_for_memory("  ") is None

    def test_clean_text_passes(self):
        assert sanitize_for_memory("user asked about routing") is not None

    def test_secret_replaced(self):
        result = sanitize_for_memory("my key is sk-" + "a" * 48)
        assert result is not None
        assert "[REDACTED]" in result

    def test_ssh_key_rejected(self):
        assert sanitize_for_memory("-----BEGIN OPENSSH PRIVATE KEY-----") is None

    def test_clean_after_redaction(self):
        result = sanitize_for_memory("api key is sk-" + "a" * 48)
        assert "[REDACTED]" in result
        assert "sk-" not in result


class TestSanitizeForDisplay:
    def test_no_secret(self):
        assert sanitize_for_display("safe text") == "safe text"

    def test_secret_redacted(self):
        result = sanitize_for_display("key: " + "x" * 20)
        assert "[REDACTED]" in result
