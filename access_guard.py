"""Private API key guard for LiMa public-compatible endpoints."""
import os

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


def _extract_token(authorization: str) -> str:
    value = (authorization or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def require_private_api_key(authorization: str = Header(default="")) -> None:
    """FastAPI dependency that fails closed unless a configured key is supplied."""
    keys = configured_api_keys()
    if not keys:
        raise HTTPException(
            status_code=503,
            detail="LiMa private API key is not configured.",
        )
    if _extract_token(authorization) not in keys:
        raise HTTPException(status_code=401, detail="Unauthorized")
