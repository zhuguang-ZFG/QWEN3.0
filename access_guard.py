"""Private API key guard for LiMa public-compatible endpoints."""

import os
import secrets

from fastapi import Header, HTTPException


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


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison using secrets.compare_digest."""
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_private_api_key(authorization: str = Header(default="")) -> None:
    """FastAPI dependency that fails closed unless a configured key is supplied.

    When ``LIMA_ALLOW_ANONYMOUS=1`` is set and at least one private key is
    configured, requests without an Authorization header are allowed.  Explicit
    keys are still validated when present.
    """
    keys = configured_api_keys()
    if not keys:
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )

    token = extract_bearer_token(authorization)
    if not token:
        if allow_anonymous_access():
            return
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not any(constant_time_equals(token, k) for k in keys):
        raise HTTPException(status_code=401, detail="Unauthorized")
