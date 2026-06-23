"""Tests for session_memory/redact.py — secret/PII detection."""

from session_memory.redact import (
    has_secret,
    redact_text,
    sanitize_for_memory,
    sanitize_for_display,
)


class TestHasSecret:
    def test_empty_text(self):
        assert has_secret("") is False

    def test_openai_key(self):
        assert has_secret("my key is sk-123456789012345678901234567890") is True

    def test_jwt_token(self):
        assert has_secret("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc") is True

    def test_bearer_token(self):
        assert has_secret("Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234") is True

    def test_key_assignment(self):
        assert has_secret("API_KEY=abcdefghijklmnopqrstuvwxyz") is True

    def test_no_secret(self):
        assert has_secret("hello world") is False

    def test_credential_url(self):
        assert has_secret("https://user:pass@example.com") is True

    def test_ssh_key(self):
        assert has_secret("-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----") is True


class TestRedactText:
    def test_redacts_openai_key(self):
        text = "sk-123456789012345678901234567890"
        assert "[REDACTED]" in redact_text(text)

    def test_redacts_credential_url(self):
        text = "https://user:pass@example.com"
        assert "[REDACTED_URL]" in redact_text(text)

    def test_redacts_ssh_key(self):
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----"
        assert "[REDACTED_KEY]" in redact_text(text)

    def test_returns_original_when_no_secret(self):
        text = "hello world"
        assert redact_text(text) == text


class TestSanitizeForMemory:
    def test_rejects_ssh_key(self):
        text = "-----BEGIN OPENSSH PRIVATE KEY-----\nkey\n-----END OPENSSH PRIVATE KEY-----"
        assert sanitize_for_memory(text) is None

    def test_rejects_empty_text(self):
        assert sanitize_for_memory("") is None
        assert sanitize_for_memory("   ") is None

    def test_redacts_secrets(self):
        result = sanitize_for_memory("my key is sk-123456789012345678901234567890")
        assert "[REDACTED]" in result


class TestSanitizeForDisplay:
    def test_redacts_secret(self):
        result = sanitize_for_display("my key is sk-123456789012345678901234567890")
        assert "[REDACTED]" in result
