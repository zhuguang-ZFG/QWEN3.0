"""HMAC tokens for time-limited upload file access."""

from __future__ import annotations

import hashlib
import hmac
import os
import time


def _secret() -> bytes:
    raw = os.environ.get("LIMA_UPLOAD_TOKEN_SECRET") or os.environ.get("LIMA_JWT_SECRET", "")
    return raw.encode()


def public_upload_get_enabled() -> bool:
    return os.environ.get("LIMA_UPLOAD_PUBLIC_GET", "0").strip().lower() in {"1", "true", "yes"}


def upload_access_token(filename: str, *, ttl_seconds: int | None = None) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else int(os.environ.get("LIMA_UPLOAD_TOKEN_TTL", "86400"))
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
