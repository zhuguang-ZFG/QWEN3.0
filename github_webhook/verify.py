"""Verify GitHub webhook HMAC signatures."""

from __future__ import annotations

import hashlib
import hmac

from access_guard import constant_time_equals


def verify_github_signature(body: bytes, signature_header: str, secret: str) -> bool:
    if not secret or not signature_header:
        return False
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False
    expected = signature_header[len(prefix):]
    if not expected:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return constant_time_equals(digest, expected)
