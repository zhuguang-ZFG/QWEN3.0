"""DLC API dependencies.

P2: verify_dlc_api_token prioritises DB table v2_device_token;
LIMA_DEVICE_TOKENS env var serves as dev/emergency fallback.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

try:
    from device_logic.db import connect as _db_connect
except Exception as exc:  # pragma: no cover - graceful degradation
    logger.warning("device_logic.db unavailable; DB token lookup disabled: %s", exc)
    _db_connect = None  # type: ignore[assignment]


def _token_hash(token: str) -> str:
    """SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Sentinel returned when DB is entirely unavailable (import/connection error),
# as opposed to DB working normally but the token not found (None).
_DB_UNAVAILABLE = object()


def _lookup_token_from_db(token: str) -> str | None | object:
    """Query v2_device_token for the device_id matching *token*.

    Returns:
        str — device_id when the token is found.
        None — DB was queried successfully but the token does not exist.
        ``_DB_UNAVAILABLE`` — DB is not importable, the table does not exist,
        or any other DB error occurred (graceful degradation).
    """
    if _db_connect is None:
        logger.info("device_logic.db unavailable; skipping DB token lookup")
        return _DB_UNAVAILABLE

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
        logger.warning("DB token lookup failed (%s); falling back to env", exc)
        return _DB_UNAVAILABLE
    return None


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


def verify_dlc_api_token(authorization: str = Header(...)) -> str:
    """Verify the DLC API bearer token and return the associated device_id.

    Priority: DB table v2_device_token → LIMA_DEVICE_TOKENS env fallback.

    Raises:
        HTTPException: 401 if the token is missing or invalid.
    """
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    # 1. Try DB lookup (production path)
    device_id = _lookup_token_from_db(token)
    if isinstance(device_id, str):
        return device_id

    # 2. DB worked but token not found → reject immediately
    if device_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    # 3. DB unavailable → env-var fallback (dev/emergency)
    tokens = _load_device_tokens()
    if not tokens:
        logger.warning("DB unavailable and LIMA_DEVICE_TOKENS not configured; rejecting")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = _token_hash(token)
    device_id = next(
        (dev for raw, dev in tokens.items() if hmac.compare_digest(_token_hash(raw), token_hash)),
        None,
    )
    if not device_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    logger.warning("Token resolved via env fallback for device %s", device_id)
    return device_id
