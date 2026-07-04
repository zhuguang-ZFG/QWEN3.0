"""DLC API dependencies.

P2: verify_dlc_api_token prioritises DB table v2_device_token;
LIMA_DEVICE_TOKENS env var serves as dev/emergency fallback.
"""

from __future__ import annotations

import hashlib
import logging
import os

from fastapi import Header, HTTPException, status

try:
    from device_logic.db import connect as _db_connect
except Exception:  # pragma: no cover - graceful degradation
    _db_connect = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _token_hash(token: str) -> str:
    """SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _lookup_token_from_db(token: str) -> str | None:
    """Query v2_device_token for the device_id matching *token*.

    Returns None (graceful degradation) when:
    - device_logic.db is not importable
    - the table does not exist yet
    - any other DB error
    """
    if _db_connect is None:
        logger.info("device_logic.db unavailable; skipping DB token lookup")
        return None

    token_hash = _token_hash(token)
    try:
        with _db_connect() as conn:
            row = conn.execute(
                "SELECT device_id FROM v2_device_token WHERE token_hash=? LIMIT 1",
                (token_hash,),
            ).fetchone()
        if row is not None:
            logger.info("Token resolved via DB for device %s", row["device_id"])
            return str(row["device_id"])
    except Exception as exc:
        # Table may not exist yet (P2 placeholder); fall through to env fallback
        logger.info("DB token lookup failed (%s); falling back to env", exc)
    return None


def _load_device_tokens() -> dict[str, str]:
    """Load device tokens from LIMA_DEVICE_TOKENS env (comma-separated token:device_id pairs)."""
    raw = os.environ.get("LIMA_DEVICE_TOKENS", "")
    tokens: dict[str, str] = {}
    if not raw:
        return tokens
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        token, device_id = pair.split(":", 1)
        token = token.strip()
        device_id = device_id.strip()
        if token and device_id:
            tokens[token] = device_id
    return tokens


def verify_dlc_api_token(authorization: str = Header(...)) -> str:
    """Verify the DLC API bearer token and return the associated device_id.

    Priority: DB table v2_device_token → LIMA_DEVICE_TOKENS env fallback.

    Raises:
        HTTPException: 401 if the token is missing or invalid.
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    # 1. Try DB lookup (production path)
    device_id = _lookup_token_from_db(token)
    if device_id:
        return device_id

    # 2. Env-var fallback (dev/emergency)
    tokens = _load_device_tokens()
    if not tokens:
        logger.warning("No DB token match and LIMA_DEVICE_TOKENS not configured; rejecting")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    device_id = tokens.get(token)
    if not device_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    logger.warning("Token resolved via env fallback for device %s", device_id)
    return device_id
