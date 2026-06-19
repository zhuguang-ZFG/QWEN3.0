"""API key guards for LiMa public and internal endpoints."""

import os
import secrets

from fastapi import Header, HTTPException, WebSocket


WS_QUERY_PARAM_TOKEN_WARNING = (
    "Token supplied via query param for %s; ensure nginx access_log is off"
)


def configured_api_keys() -> set[str]:
    """Return non-empty private API keys from environment configuration."""
    keys: set[str] = set()
    primary = os.environ.get("LIMA_API_KEY", "").strip()
    if primary:
        keys.add(primary)
    for raw in os.environ.get("LIMA_API_KEYS", "").split(","):
        key = raw.strip()
        if key:
            keys.add(key)
    return keys


def is_private_access_configured() -> bool:
    """Whether LiMa has an explicit private API key configured."""
    return bool(configured_api_keys())


def allow_anonymous_access() -> bool:
    """Whether public endpoints may be used without an API key."""
    return os.environ.get("LIMA_ALLOW_ANONYMOUS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def extract_bearer_token(authorization: str) -> str:
    """Extract token from Bearer <token> header. Returns empty string on mismatch."""
    value = (authorization or "").strip()
    prefix = "Bearer "
    if value.startswith(prefix) and len(value) > len(prefix):
        return value[len(prefix) :].strip()
    return ""


def extract_websocket_token(
    websocket: WebSocket,
    query_authorization: str = "",
) -> tuple[str, bool]:
    """Extract bearer token from a WebSocket header or query param.

    Browsers cannot set custom headers on WebSocket connections, so the
    ``authorization`` query parameter is allowed as a fallback.  Returns the
    extracted token and a boolean indicating whether the query parameter was
    used.
    """
    header_token = extract_bearer_token(websocket.headers.get("authorization", ""))
    query_auth = query_authorization.strip()
    query_token = extract_bearer_token(query_auth)
    if not header_token and query_token:
        return query_token, True
    return header_token, False


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison using secrets.compare_digest."""
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def is_token_valid(token: str) -> bool:
    """Return whether a non-empty bearer token matches a configured key."""
    keys = configured_api_keys()
    if not keys or not token:
        return False
    return any(constant_time_equals(token, k) for k in keys)


def require_private_api_key(authorization: str = Header(default="")) -> None:
    """FastAPI dependency that always requires a configured private key."""
    token = extract_bearer_token(authorization)
    if is_token_valid(token):
        return
    if not configured_api_keys():
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )
    raise HTTPException(status_code=401, detail="Unauthorized")


def require_public_or_private_api_key(authorization: str = Header(default="")) -> None:
    """Public endpoint dependency that may allow anonymous demo traffic."""
    token = extract_bearer_token(authorization)
    if is_token_valid(token):
        return
    if not configured_api_keys():
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )
    if not token and allow_anonymous_access():
        return
    raise HTTPException(status_code=401, detail="Unauthorized")
