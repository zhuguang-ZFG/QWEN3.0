"""Shared utilities for XiaoZhi v1 compatibility API."""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
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

# Constants
ALLOWED_TASKS = frozenset({"run_path", "draw_image", "home", "calibrate"})
ALLOWED_SOURCES = frozenset({"api", "voice", "scheduled"})
ALLOWED_MEMBER_ROLES = frozenset({"child", "parent", "guest"})
ALLOWED_TASK_STATUSES = frozenset({"pending", "approved", "running", "completed", "failed", "cancelled", "rejected"})


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


def gateway_capability(intent: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    """Map xiaozhi intent to gateway capability."""
    if intent == "run_path":
        return "run_path", {**params, "source_capability": "run_path"}, None
    if intent == "draw_image":
        if not isinstance(params.get("path"), list):
            return "", {}, "draw_image requires params.path until imageUrl projection is wired"
        mapped = {**params, "source_capability": "draw_image"}
        if "imageUrl" in params:
            mapped["image_url"] = params["imageUrl"]
        return "run_path", mapped, None
    if intent == "home":
        return "home", {"source_capability": "home"}, None
    if intent == "calibrate":
        return "home", {"source_capability": "calibrate"}, None
    return "", {}, f"unsupported capability: {intent}"


def build_gateway_task(device_id: str, intent: str, params: dict[str, Any], source: str, request_id: str) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    """Build gateway task from xiaozhi intent."""
    from device_gateway.path_validator import validate_capability_params
    from device_intelligence.schemas import TaskPlan
    from device_intelligence.simulator import simulate_motion
    from device_policy import policy_engine
    from device_workflow.orchestrator import workflow
    from device_workflow.state import TaskState

    capability, gateway_params, error = gateway_capability(intent, params)
    if error:
        return None, err(4001, error, 400)
    sanitized, validation_error = validate_capability_params(capability, gateway_params)
    if validation_error:
        return None, err(4002, f"validation failed: {validation_error}", 400)
    policy = policy_engine.decide(capability=capability, device_id=device_id, fw_rev="", params=sanitized)
    if policy.decision != "allow":
        return None, err(4003, policy.reason, 400)
    task_id = f"task-{uuid4().hex[:12]}"
    workflow.register(task_id)
    workflow.advance(task_id, TaskState.PLANNED)
    sim = simulate_motion(TaskPlan(plan_id=f"sim-{task_id}", device_id=device_id, capability=capability, params=sanitized))
    workflow.advance(task_id, TaskState.SIMULATED)
    needs_approval = bool(source == "voice" and params.get("requireApproval")) or sim.risk_score >= 0.7
    workflow.advance(task_id, TaskState.WAITING_APPROVAL if needs_approval else TaskState.READY_TO_DISPATCH)
    task = {
        "type": "motion_task",
        "task_id": task_id,
        "device_id": device_id,
        "capability": capability,
        "source": source,
        "params": sanitized,
        "policy": policy.to_dict(),
        "simulation": sim.to_dict(),
        "workflow_state": TaskState.WAITING_APPROVAL.value if needs_approval else TaskState.READY_TO_DISPATCH.value,
        "compat": {"intent": intent},
    }
    if request_id:
        task["request_id"] = request_id
    from device_gateway import store as store_mod
    store_mod.task_store.create_task_state(task, status="created")
    return task, None


async def dispatch_or_enqueue(device_id: str, task: dict[str, Any]) -> dict[str, Any]:
    """Dispatch task to session or enqueue."""
    from device_gateway.sessions import registry
    from device_gateway.tasks import enqueue_pending_task
    from routes.device_gateway_dispatch import dispatch_task_to_session, publish_task_available_safe

    session = registry.get(device_id)
    sent = False
    if session is not None:
        sent = await dispatch_task_to_session(session, task)
    queue_depth = 0
    if not sent:
        queue_depth = enqueue_pending_task(device_id, task)
        await publish_task_available_safe(device_id, str(task.get("task_id", "")))
    return {"sent": sent, "queueDepth": queue_depth, "dispatchStatus": "sent" if sent else "queued"}


def voiceprint_payload(row: sqlite3.Row, member_name: str = "") -> dict[str, Any]:
    """Convert voiceprint row to API payload."""
    return {
        "voiceprintId": row["id"],
        "id": row["id"],
        "memberId": row["member_id"],
        "memberName": member_name,
        "deviceId": row["device_id"],
        "sampleCount": row["sample_count"],
        "confidence": row["confidence"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def transfer_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert transfer row to API payload."""
    return {
        "transferId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "fromAccountId": row["from_account_id"],
        "toAccountId": row["to_account_id"],
        "status": row["status"],
        "reason": row["reason"],
        "expiresAt": row["expires_at"],
        "acceptedAt": row["accepted_at"],
        "cancelledAt": row["cancelled_at"],
        "createdAt": row["created_at"],
    }


def supply_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert supply row to API payload."""
    return {
        "supplyId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "supplyType": row["supply_type"],
        "level": row["level"],
        "status": row["status"],
        "lastReplaced": row["last_replaced"],
        "nextReplacement": row["next_replacement"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def self_check_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert self-check row to API payload."""
    return {
        "id": row["id"],
        "deviceId": row["device_id"],
        "checkType": row["check_type"],
        "result": row["result"],
        "details": row["details"],
        "durationMs": row["duration_ms"],
        "triggeredBy": row["triggered_by"],
        "createdAt": row["created_at"],
    }


def expires_at(seconds: int) -> str:
    """Calculate expiration timestamp."""
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=seconds))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def expire_pending_transfers(conn: sqlite3.Connection) -> None:
    """Mark expired transfers."""
    conn.execute(
        "UPDATE v2_device_transfer_request SET status='expired' WHERE status='pending' AND expires_at <= ?",
        (now(),),
    )


def is_owner(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
    """Check if account is device owner."""
    if account.get("role") == "admin":
        return True
    row = conn.execute(
        """
        SELECT 1 FROM v2_device_binding
        WHERE device_id=? AND account_id=? AND bind_mode='owner' AND status='active'
        """,
        (device_id, account["id"]),
    ).fetchone()
    return row is not None


def parse_supply_updates(body: dict[str, Any]) -> tuple[list[dict[str, Any]], JSONResponse | None]:
    """Parse supply update request body."""
    raw_items: list[dict[str, Any]] = []
    if isinstance(body.get("supplies"), list):
        raw_items.extend(item for item in body["supplies"] if isinstance(item, dict))
    direct_type = str_field(body, "supplyType", "supply_type")
    if direct_type:
        raw_items.append(body)
    for supply_type in ("pen", "paper", "battery"):
        value = body.get(supply_type)
        if isinstance(value, dict):
            raw_items.append({"supplyType": supply_type, **value})
    updates: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        supply_type = str_field(item, "supplyType", "supply_type")
        status = str_field(item, "status") or "unknown"
        if not supply_type:
            return [], err(400, "supplyType is required", 400)
        if status not in {"normal", "low", "empty", "unknown"}:
            return [], err(400, "invalid supply status", 400)
        try:
            level = float(item.get("level", 1.0))
        except (TypeError, ValueError):
            return [], err(400, "supply level must be numeric", 400)
        if not 0.0 <= level <= 1.0:
            return [], err(400, "supply level must be between 0.0 and 1.0", 400)
        updates[supply_type] = {"supply_type": supply_type, "level": level, "status": status}
    if not updates:
        return [], err(400, "at least one supply update is required", 400)
    return list(updates.values()), None
