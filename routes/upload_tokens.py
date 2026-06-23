"""HMAC tokens for time-limited upload file access."""

from __future__ import annotations

import hashlib
import hmac
import time

from config.env import (
    upload_public_get_enabled as _env_upload_public_get_enabled,
    upload_token_secret as _env_upload_token_secret,
    upload_token_ttl as _env_upload_token_ttl,
)


def _secret() -> bytes:
    return _env_upload_token_secret()


def public_upload_get_enabled() -> bool:
    return _env_upload_public_get_enabled()


def upload_access_token(filename: str, *, ttl_seconds: int | None = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else _env_upload_token_ttl()
    exp = int(time.time()) + ttl
    sig = hmac.new(_secret(), f"{filename}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def verify_upload_access_token(filename: str, token: str) -> bool:
    if not token or not _secret():
        return False
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except ValueError:
        return False
    if exp < int(time.time()):
        return False
    expected = hmac.new(_secret(), f"{filename}:{exp}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
