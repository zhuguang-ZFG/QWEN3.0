"""Private API key guard for LiMa public-compatible endpoints."""
import logging
import os
import secrets

from fastapi import Header, HTTPException

_log = logging.getLogger(__name__)


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


def extract_bearer_token(authorization: str) -> str:
    """Extract token from Bearer <token> header. Returns empty string on mismatch."""
    value = (authorization or "").strip()
    prefix = "Bearer "
    if value.startswith(prefix) and len(value) > len(prefix):
        return value[len(prefix):].strip()
    return ""


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison using secrets.compare_digest."""
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_private_api_key(
    authorization: str = Header(default=""),
    request: object = None,
) -> None:
    """FastAPI dependency that fails closed unless a configured key is supplied.

    Checks static environment keys first, then dynamic client keys from the store.
    Returns 503 if no authentication source is configured at all.
    """
    keys = configured_api_keys()
    token = extract_bearer_token(authorization)

    if not token:
        if not keys:
            raise HTTPException(
                status_code=503,
                detail="LiMa private API key is not configured.",
            )
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 1. Check static environment keys (backward compatible)
    if keys and any(constant_time_equals(token, k) for k in keys):
        return

    # 2. Check dynamic client keys from the store
    client_key = None
    try:
        from routes.admin_client_keys import find_client_key, try_consume_quota, check_allowed_urls

        client_key = find_client_key(token)
    except ImportError:
        _log.debug("access_guard: admin_client_keys not available")

    if client_key is not None:
        if not client_key.get("enabled", False):
            raise HTTPException(status_code=403, detail="API key is disabled")
        # URL restriction check (if request object available)
        if request is not None and hasattr(request, "url"):
            if not check_allowed_urls(client_key, request.url.path):
                raise HTTPException(status_code=403, detail="URL not allowed for this key")
        # Atomic quota + RPM check and consumption
        allowed, reason = try_consume_quota(client_key)
        if not allowed:
            detail = {
                "daily_limit": "API key daily quota exceeded",
                "monthly_limit": "API key monthly quota exceeded",
                "rpm_limit": "API key rate limit (RPM) exceeded",
            }.get(reason, "API key quota exceeded")
            raise HTTPException(status_code=429, detail=detail)
        return

    # No matching key found
    if not keys:
        # No static keys AND no client key matched — fail closed
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )
    raise HTTPException(status_code=401, detail="Unauthorized")
