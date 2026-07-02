"""Admin user authentication (email/password + JWT).

This is separate from the device-app ``v2_account`` table so that console
admins can have their own credentials and role model without affecting the
mobile/mini-program auth flow.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any

from config import settings
from device_logic.db import connect
from device_logic.http import new_id

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


ADMIN_ROLES = {"admin", "superadmin"}


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
        _log.warning("password hash is malformed; treating as authentication failure: %s", exc)
        return False
    except Exception as exc:
        _log.error("password verification encountered an error; treating as failure: %s", exc, exc_info=True)
        return False


def _jwt_secret() -> str | None:
    secret = getattr(settings.SECURITY, "jwt_secret", None)
    if secret:
        return secret
    _log.warning("LIMA_JWT_SECRET is not configured; admin JWT auth is unavailable")
    return None


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the admin_users table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname      TEXT,
            role          TEXT DEFAULT 'admin'
                CHECK (role IN ('admin', 'superadmin')),
            status        TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'disabled')),
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email)")


def create_admin_user(email: str, password: str, nickname: str = "", role: str = "admin") -> dict[str, Any]:
    """Create a new admin user. Requires bcrypt to be installed."""
    if "@" not in email or len(email) < 5:
        raise ValueError("invalid email")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if role not in ADMIN_ROLES:
        raise ValueError(f"role must be one of {ADMIN_ROLES}")

    with connect() as conn:
        _ensure_table(conn)
        existing = conn.execute("SELECT id FROM admin_users WHERE email=?", (email,)).fetchone()
        if existing is not None:
            raise ValueError("admin user with this email already exists")
        user_id = new_id()
        conn.execute(
            """
            INSERT INTO admin_users (id, email, password_hash, nickname, role)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, email, _hash_password(password), nickname, role),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM admin_users WHERE id=?", (user_id,)).fetchone()
        return dict(row)


def authenticate_admin(email: str, password: str) -> dict[str, Any] | None:
    """Verify email/password and return the active admin user row, or None."""
    with connect() as conn:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT * FROM admin_users WHERE email=? AND status='active'",
            (email,),
        ).fetchone()
    if row is None:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return dict(row)


def make_admin_token(user: dict[str, Any] | sqlite3.Row, expires_in: int = 86400) -> str | None:
    """Issue a JWT for an admin user."""
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return None
    secret = _jwt_secret()
    if not secret:
        return None
    now_ts = int(time.time())
    payload = {
        "sub": user["id"],
        "account_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "iat": now_ts,
        "exp": now_ts + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_admin_token(token: str) -> dict[str, Any] | None:
    """Decode and validate an admin JWT. Returns None on any failure."""
    if jwt is None:
        return None
    secret = _jwt_secret()
    if not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def admin_payload(user: dict[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "nickname": user["nickname"],
        "role": user["role"],
        "status": user["status"],
        "createdAt": user["created_at"],
    }
