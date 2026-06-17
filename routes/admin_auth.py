"""Admin authentication helpers."""

import hashlib
import hmac
import os
import secrets
from urllib.parse import urlparse

from fastapi import Cookie, Header, HTTPException, Request


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
    return bool(token and value and secrets.compare_digest(value, admin_session_value()))


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
    # Require strict Bearer token with constant-time comparison
    from access_guard import extract_bearer_token, constant_time_equals

    presented = extract_bearer_token(authorization)
    if not presented or not constant_time_equals(presented, token_expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _header_hostname(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    return (parsed.hostname or "").lower()


async def verify_csrf(
    request: Request,
    authorization: str = Header(default=""),
    origin: str = Header(default=""),
    referer: str = Header(default=""),
) -> None:
    """CSRF guard for mutating admin endpoints.

    Browsers send Origin/Referer on cross-origin requests. We verify:
    - API clients using Authorization header are exempt (they can't be CSRF'd)
    - Cookie-only clients must have Origin/Referer hostname matching request host
    """
    from access_guard import extract_bearer_token

    if extract_bearer_token(authorization):
        return
    expected = (request.url.hostname or "").lower()
    if not expected:
        raise HTTPException(status_code=403, detail="CSRF: cannot determine host")
    for header_val in (origin, referer):
        if _header_hostname(header_val) == expected:
            return
    raise HTTPException(status_code=403, detail="CSRF: Origin/Referer mismatch")
