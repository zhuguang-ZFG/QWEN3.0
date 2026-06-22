"""API key guards for LiMa public and internal endpoints."""

import logging
import os
import secrets

from fastapi import Header, HTTPException, WebSocket

import ws_ticket
from runtime_env import is_production_runtime

_log = logging.getLogger(__name__)

# ponytail: WS_QUERY_PARAM_TOKEN_WARNING — logged on every legacy query-param auth use so
# nginx/log-pipelines can surface deprecation drift before the path is removed.
WS_QUERY_PARAM_TOKEN_WARNING = "Token supplied via query param for %s; ensure nginx access_log is off"


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


def _anonymous_access_env_enabled() -> bool:
    return os.environ.get("LIMA_ALLOW_ANONYMOUS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def allow_anonymous_access() -> bool:
    """Whether public endpoints may be used without an API key."""
    return _anonymous_access_env_enabled()


def anonymous_access_status() -> dict[str, bool]:
    """Health/ops snapshot for anonymous demo access configuration."""
    env_enabled = _anonymous_access_env_enabled()
    production = is_production_runtime()
    allowed = allow_anonymous_access()
    return {
        "allowed": allowed,
        "env_enabled": env_enabled,
        "production_blocked": production and env_enabled and not allowed,
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
    """Extract bearer token from a WebSocket header or legacy query param.

    Prefer ``authenticate_websocket()`` for new code; it also accepts one-time
    ``?ticket=`` values from ``POST /v1/ws/ticket``.
    """
    header_token = extract_bearer_token(websocket.headers.get("authorization", ""))
    query_auth = query_authorization.strip()
    query_token = extract_bearer_token(query_auth)
    if not header_token and query_token:
        return query_token, True
    return header_token, False


def authenticate_websocket(
    websocket: WebSocket,
    query_authorization: str = "",
) -> tuple[bool, str]:
    """Authorize a WebSocket connection.

    Returns ``(authorized, method)`` where method is ``header``, ``ticket``,
    ``query`` (legacy), or ``none``.
    """
    header_token = extract_bearer_token(websocket.headers.get("authorization", ""))
    if is_token_valid(header_token):
        return True, "header"

    ticket = websocket.query_params.get("ticket", "").strip()
    if ticket and ws_ticket.consume(ticket):
        return True, "ticket"

    query_token = extract_bearer_token(query_authorization.strip())
    if query_token and is_token_valid(query_token):
        # ponytail: legacy path — warn on every use so log-pipelines catch deprecation drift.
        _log.warning(WS_QUERY_PARAM_TOKEN_WARNING, websocket.url.path)
        return True, "query"

    return False, "none"


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
