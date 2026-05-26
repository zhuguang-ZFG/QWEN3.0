"""Verify Gitee WebHook requests (password token or signed timestamp)."""

from __future__ import annotations

import base64
import hashlib
import hmac

from access_guard import constant_time_equals


def verify_gitee_token(token: str, secret: str) -> bool:
    if not token or not secret:
        return False
    return constant_time_equals(token.strip(), secret.strip())


def verify_gitee_sign(timestamp: str, sign: str, secret: str) -> bool:
    """Gitee sign = base64(HMAC-SHA256(secret, timestamp))."""
    if not timestamp or not sign or not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8"), hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return constant_time_equals(sign.strip(), expected)


def verify_gitee_request(
    *,
    token_header: str,
    payload: dict,
    secret: str,
    timestamp_header: str = "",
) -> bool:
    if not secret:
        return False
    password = str(payload.get("password") or "")
    if verify_gitee_token(token_header, secret):
        return True
    if password and verify_gitee_token(password, secret):
        return True
    timestamp = str(timestamp_header or payload.get("timestamp") or "")
    sign = str(payload.get("sign") or "")
    if sign and timestamp and verify_gitee_sign(timestamp, sign, secret):
        return True
    if sign and token_header and verify_gitee_sign(timestamp, token_header, secret):
        return True
    return False
