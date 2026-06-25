"""JWT authentication for LiMa device app accounts."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

from access_guard import extract_bearer_token
from config import settings
from fastapi.responses import JSONResponse

from device_logic.db import connect
from device_logic.http import err

try:
    import jwt
except ImportError as exc:
    jwt = None
    _JWT_IMPORT_ERROR: ImportError | None = exc
else:
    _JWT_IMPORT_ERROR = None

try:
    import bcrypt
except ImportError as exc:
    bcrypt = None
    _BCRYPT_IMPORT_ERROR: ImportError | None = exc
else:
    _BCRYPT_IMPORT_ERROR = None

_log = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    if bcrypt is None:
        raise RuntimeError(f"bcrypt is required for password hashing: {_BCRYPT_IMPORT_ERROR}")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    if bcrypt is None:
        _log.warning("bcrypt is not installed: %s", _BCRYPT_IMPORT_ERROR)
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError as exc:
        # Malformed hash: still deny access, but log a warning so operators can
        # detect storage corruption or bad imports.
        _log.warning("password hash is malformed; treating as authentication failure: %s", exc)
        return False
    except Exception as exc:
        _log.error("password verification encountered an error; treating as failure: %s", exc, exc_info=True)
        return False


def jwt_secret() -> str | None:
    secret = settings.SECURITY.jwt_secret
    if secret:
        return secret
    _log.warning("LIMA_JWT_SECRET is not configured; device app JWT auth is unavailable")
    return None


def make_token(account: sqlite3.Row, expires_in: int = 86400) -> str | None:
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return None
    secret = jwt_secret()
    if not secret:
        return None
    now_ts = int(time.time())
    payload = {
        "sub": account["id"],
        "account_id": account["id"],
        "phone": account["phone"],
        "role": account["role"],
        "iat": now_ts,
        "exp": now_ts + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def authorize(authorization: str) -> dict[str, Any] | JSONResponse:
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return err(503, "JWT support is not installed", 503)
    secret = jwt_secret()
    if not secret:
        return err(503, "JWT secret is not configured", 503)
    token = extract_bearer_token(authorization)
    if not token:
        return err(401, "Unauthorized", 401)
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return err(401, "Token expired", 401)
    except jwt.InvalidTokenError:
        return err(401, "Unauthorized", 401)
    account_id = str(payload.get("account_id") or payload.get("sub") or "")
    if not account_id:
        return err(401, "Unauthorized", 401)
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM v2_account WHERE id=? AND status='active'",
            (account_id,),
        ).fetchone()
    if row is None:
        return err(401, "Unauthorized", 401)
    return dict(row)


def account_payload(account: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "accountId": account["id"],
        "phone": account["phone"],
        "email": account["email"],
        "nickname": account["nickname"],
        "avatarUrl": account["avatar_url"],
        "role": account["role"],
        "createdAt": account["created_at"],
    }
