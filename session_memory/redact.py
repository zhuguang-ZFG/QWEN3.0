"""Memory Redaction - secret and PII detection for session memory.

Usable by both the memory daemon (inbox ingestion) and request-time
memory writes (save_memory / save_typed_memory).

Patterns:
    - API keys (sk-, ghp_, xai-, AKIA, etc.)
    - JWT tokens (eyJ...)
    - Bearer tokens
    - Key/token/secret/password literals
    - URLs containing credentials
    - Private SSH keys
"""

import re
import logging

logger = logging.getLogger("memory_redact")

# Secret patterns

_SECRET_RE = re.compile(
    r'(sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9\-]{20,}|'
    r'ghp_[a-zA-Z0-9]{36,}|xai-[a-zA-Z0-9]{20,}|'
    r'AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35}|'
    r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+|'
    r'Bearer\s+[a-zA-Z0-9._\-/+=]{20,}|'
    r'(?:key|token|secret|password|apikey|api_key)\s*[=:]\s*\S{16,})',
    re.IGNORECASE,
)

_CREDENTIAL_URL_RE = re.compile(
    r'https?://[^@\s]+:[^@\s]+@\S+', re.IGNORECASE
)

_SSH_KEY_RE = re.compile(
    r'-----BEGIN\s+(?:RSA|OPENSSH|DSA|EC|PGP)\s+PRIVATE KEY-----',
    re.IGNORECASE,
)


def has_secret(text: str) -> bool:
    """Check if text contains secret-like patterns."""
    if _SECRET_RE.search(text):
        return True
    if _CREDENTIAL_URL_RE.search(text):
        return True
    if _SSH_KEY_RE.search(text):
        return True
    return False


def redact_text(text: str) -> str:
    """Replace detected secrets with [REDACTED] markers. Returns cleaned text."""
    text = _SECRET_RE.sub("[REDACTED]", text)
    text = _CREDENTIAL_URL_RE.sub("[REDACTED_URL]", text)
    text = _SSH_KEY_RE.sub("[REDACTED_KEY]", text)
    return text


def sanitize_for_memory(text: str) -> str | None:
    """Sanitize text before storage.

    Returns None if the text should be rejected entirely
    (contains critical secrets that can't be safely cleaned).
    Returns the cleaned text otherwise.
    """
    if not text or not text.strip():
        return None
    if _SSH_KEY_RE.search(text):
        logger.warning("[MemoryRedact] private key detected, rejecting")
        return None
    cleaned = redact_text(text)
    if cleaned != text:
        logger.info("[MemoryRedact] secrets redacted from memory text")
    return cleaned


def sanitize_for_display(text: str) -> str:
    """Sanitize text before displaying to user or exporting."""
    return redact_text(text)
