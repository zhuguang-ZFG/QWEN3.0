"""Shared utilities for XiaoZhi v1 compatibility API."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from access_guard import extract_bearer_token

try:
    import jwt
    _JWT_IMPORT_ERROR = None
except ImportError as e:
    jwt = None
    _JWT_IMPORT_ERROR = str(e)

_log = logging.getLogger(__name__)
_schema_lock = threading.Lock()
_schema_ready_paths: set[str] = set()


def ok(data: Any) -> JSONResponse:
    """Success response."""
    return JSONResponse({"code": 0, "data": data})


def err(code: int, message: str, status_code: int = 400) -> JSONResponse:
    """Error response."""
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


async def read_body(request: Request) -> dict[str, Any] | JSONResponse:
    """Read and validate JSON body."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return err(400, "valid JSON body required", 400)
    if not isinstance(body, dict):
        return err(400, "JSON object body required", 400)
    return body


def db_path() -> Path:
    """Get database path."""
    return Path(os.environ.get("LIMA_DB_PATH", "data/lima.db"))


def connect() -> sqlite3.Connection:
    """Connect to database with schema initialization."""
    path = db_path()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_schema(conn, str(path.resolve()))
    return conn


def ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    """Ensure database schema is initialized."""
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        _schema_ready_paths.add(resolved_path)


def jwt_secret() -> str | None:
    """Get JWT secret from environment."""
    secret = os.environ.get("LIMA_JWT_SECRET", "").strip()
    if secret:
        return secret
    _log.warning("LIMA_JWT_SECRET is not configured; xiaozhi JWT auth is unavailable")
    return None


def make_token(account: sqlite3.Row, expires_in: int = 86400) -> str | None:
    """Generate JWT token."""
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return None
    secret = jwt_secret()
    if not secret:
        return None
    now = int(time.time())
    payload = {
        "sub": account["id"],
        "account_id": account["id"],
        "phone": account["phone"],
        "role": account["role"],
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def account_payload(account: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Convert account row to API payload."""
    return {
        "accountId": account["id"],
        "phone": account["phone"],
        "nickname": account["nickname"],
        "avatarUrl": account["avatar_url"],
        "role": account["role"],
        "createdAt": account["created_at"],
    }


def authorize(authorization: str) -> dict[str, Any] | JSONResponse:
    """Authorize request via JWT."""
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
        row = conn.execute("SELECT * FROM v2_account WHERE id=? AND status='active'", (account_id,)).fetchone()
    if row is None:
        return err(401, "Unauthorized", 401)
    return dict(row)


def now() -> str:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    """Generate new UUID."""
    return str(uuid4())


def str_field(body: dict[str, Any], *names: str) -> str:
    """Extract first non-empty string field."""
    for name in names:
        value = body.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def query_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Parse and clamp integer."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def json_params(value: Any) -> str:
    """Serialize params to JSON."""
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, sort_keys=True)


def loads_json(value: Any) -> dict[str, Any]:
    """Parse JSON string to dict."""
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def device_access(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
    """Check device access permission."""
    if account.get("role") == "admin":
        return True
    row = conn.execute(
        "SELECT 1 FROM v2_device_binding WHERE device_id=? AND account_id=? AND status='active'",
        (device_id, account["id"]),
    ).fetchone()
    return row is not None


def require_device_access(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> JSONResponse | None:
    """Require device access or return error."""
    if not device_access(conn, account, device_id):
        return err(403, "Device is not bound to this account", 403)
    return None


def device_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert device row to API payload."""
    return {
        "id": row["id"],
        "deviceId": row["id"],
        "deviceSn": row["device_sn"],
        "model": row["model"],
        "firmwareVer": row["firmware_ver"],
        "hardwareVer": row["hardware_ver"],
        "status": row["status"],
        "lastHeartbeat": row["last_heartbeat"],
        "mqttTopic": row["mqtt_topic"],
        "metadata": row["metadata"],
    }


def task_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert task row to API payload."""
    return {
        "taskId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "capability": row["intent"],
        "params": loads_json(row["params"]),
        "source": row["source"],
        "status": row["status"],
        "progress": row["progress"],
        "errorMsg": row["error_msg"],
        "memberId": row["member_id"],
        "createdAt": row["created_at"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
    }


def member_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert member row to API payload."""
    return {
        "memberId": row["id"],
        "id": row["id"],
        "accountId": row["account_id"],
        "deviceId": row["device_id"],
        "name": row["name"],
        "role": row["role"],
        "avatarUrl": row["avatar_url"],
        "voiceprintId": row["voiceprint_id"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }
