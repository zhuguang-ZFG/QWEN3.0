"""Admin authentication helpers."""

import hashlib
import hmac
import os
import secrets

from fastapi import Cookie, Header, HTTPException


SESSION_COOKIE = "lima_admin_session"
_ADMIN_TOKEN = os.environ.get("LIMA_ADMIN_TOKEN", "")


def get_admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "") or _ADMIN_TOKEN


def admin_session_value() -> str:
    token = get_admin_token()
    return hmac.new(
        token.encode("utf-8"),
        b"lima-admin-session",
        hashlib.sha256,
    ).hexdigest()


def is_valid_admin_session(value: str) -> bool:
    token = get_admin_token()
    return bool(
        token
        and value
        and secrets.compare_digest(value, admin_session_value())
    )


async def verify_admin(
    authorization: str = Header(default=""),
    lima_admin_session: str = Cookie(default=""),
) -> None:
    token_expected = get_admin_token()
    if not token_expected:
        raise HTTPException(
            status_code=503,
            detail="LiMa admin token is not configured.",
        )
    if is_valid_admin_session(lima_admin_session):
        return
    if authorization != f"Bearer {token_expected}" and authorization != token_expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
