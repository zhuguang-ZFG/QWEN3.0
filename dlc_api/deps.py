"""DLC API dependencies.

P2: verify_dlc_api_token prioritises DB table v2_device_token;
LIMA_DEVICE_TOKENS env var serves as dev/emergency fallback.
"""

from __future__ import annotations

import hmac
import logging
import os

from fastapi import Header, HTTPException, status
from runtime_env import is_production_runtime

from device_logic.device_token import DB_UNAVAILABLE, lookup_device_id_by_token, token_hash

logger = logging.getLogger(__name__)


def _load_device_tokens() -> dict[str, str]:
    """Load device tokens from LIMA_DEVICE_TOKENS env.

    Supports two formats:
    - ``token:device_id`` (DLC native)
    - ``device_id=token`` (device-gateway compatible, used on VPS)

    Multiple entries are comma-separated.
    """
    raw = os.environ.get("LIMA_DEVICE_TOKENS", "")
    tokens: dict[str, str] = {}
    if not raw:
        return tokens
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            token, device_id = pair.split(":", 1)
        elif "=" in pair:
            device_id, token = pair.split("=", 1)
        else:
            continue
        token = token.strip()
        device_id = device_id.strip()
        if token and device_id:
            tokens[token] = device_id
    return tokens


def _env_fallback_device_id(token: str) -> str:
    """Resolve token via env when DB is unavailable; may raise HTTPException."""
    allow = os.environ.get("LIMA_DLC_ALLOW_ENV_TOKEN_FALLBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if is_production_runtime() and not allow:
        logger.error("DB token lookup unavailable in production; rejecting without break-glass flag")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication backend unavailable"
        )
    tokens = _load_device_tokens()
    if not tokens:
        logger.warning("DB unavailable and LIMA_DEVICE_TOKENS not configured; rejecting")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    digest = token_hash(token)
    resolved = next(
        (dev for raw, dev in tokens.items() if hmac.compare_digest(token_hash(raw), digest)),
        None,
    )
    if not resolved:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    logger.warning("Token resolved via env fallback for device %s", resolved)
    return resolved


def verify_dlc_api_token(authorization: str = Header(...)) -> str:
    """Verify the DLC API bearer token and return the associated device_id.

    Priority: DB table v2_device_token → LIMA_DEVICE_TOKENS env fallback.
    """
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    device_id = lookup_device_id_by_token(token)
    if isinstance(device_id, str):
        logger.info("Token resolved via DB for device %s", device_id)
        return device_id
    if device_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if device_id is not DB_UNAVAILABLE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _env_fallback_device_id(token)
