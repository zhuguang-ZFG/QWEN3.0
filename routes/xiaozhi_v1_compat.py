"""XiaoZhi v1 compatibility API for LiMa smart-device clients.

Provides the P0/P1 endpoints that the XiaoZhi Java server previously served,
backed by SQLite (v2_* tables) and the existing device_gateway pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from access_guard import extract_bearer_token
from device_gateway.path_validator import validate_capability_params
from device_gateway.sessions import registry
from device_gateway.tasks import enqueue_pending_task, record_motion_event, task_snapshot
from device_intelligence.schemas import TaskPlan
from device_intelligence.simulator import simulate_motion
from device_policy import policy_engine
from device_workflow.orchestrator import workflow
from device_workflow.state import TaskState, WorkflowTransitionError
from routes.device_gateway_dispatch import dispatch_task_to_session, publish_task_available_safe

try:
    import jwt
except ImportError as exc:
    jwt = None
    _JWT_IMPORT_ERROR: ImportError | None = exc
else:
    _JWT_IMPORT_ERROR = None

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["xiaozhi-v1-compat"])
_schema_lock = threading.Lock()
_schema_ready_paths: set[str] = set()
_activation_warning_logged = False

_ALLOWED_TASKS = frozenset({"run_path", "draw_image", "home", "calibrate"})
_ALLOWED_SOURCES = frozenset({"api", "voice", "scheduled"})
_ALLOWED_MEMBER_ROLES = frozenset({"child", "parent", "guest"})
_ALLOWED_TASK_STATUSES = frozenset({"pending", "approved", "running", "completed", "failed", "cancelled", "rejected"})
_ACTIVATION_TTL_SECONDS = 600
_activation_codes: dict[str, dict[str, Any]] = {}
_activation_lock = threading.Lock()


def _ok(data: Any) -> JSONResponse:
    return JSONResponse({"code": 0, "data": data})


def _err(code: int, message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


async def _read_body(request: Request) -> dict[str, Any] | JSONResponse:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return _err(400, "valid JSON body required", 400)
    if not isinstance(body, dict):
        return _err(400, "JSON object body required", 400)
    return body


def _db_path() -> Path:
    return Path(os.environ.get("LIMA_DB_PATH", "data/lima.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn, str(path.resolve()))
    return conn


def _ensure_schema(conn: sqlite3.Connection, resolved_path: str) -> None:
    with _schema_lock:
        if resolved_path in _schema_ready_paths:
            return
        schema_path = Path(__file__).resolve().parent.parent / "migrations" / "xiaozhi_schema.sql"
        if not schema_path.exists():
            raise RuntimeError(f"xiaozhi schema missing: {schema_path}")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
        _schema_ready_paths.add(resolved_path)


def _jwt_secret() -> str | None:
    secret = os.environ.get("LIMA_JWT_SECRET", "").strip()
    if secret:
        return secret
    _log.warning("LIMA_JWT_SECRET is not configured; xiaozhi JWT auth is unavailable")
    return None


def _make_token(account: sqlite3.Row, expires_in: int = 86400) -> str | None:
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return None
    secret = _jwt_secret()
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


def _account_payload(account: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "accountId": account["id"],
        "phone": account["phone"],
        "nickname": account["nickname"],
        "avatarUrl": account["avatar_url"],
        "role": account["role"],
        "createdAt": account["created_at"],
    }


def _authorize(authorization: str) -> dict[str, Any] | JSONResponse:
    if jwt is None:
        _log.warning("PyJWT is not installed: %s", _JWT_IMPORT_ERROR)
        return _err(503, "JWT support is not installed", 503)
    secret = _jwt_secret()
    if not secret:
        return _err(503, "JWT secret is not configured", 503)
    token = extract_bearer_token(authorization)
    if not token:
        return _err(401, "Unauthorized", 401)
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return _err(401, "Token expired", 401)
    except jwt.InvalidTokenError:
        return _err(401, "Unauthorized", 401)
    account_id = str(payload.get("account_id") or payload.get("sub") or "")
    if not account_id:
        return _err(401, "Unauthorized", 401)
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE id=? AND status='active'", (account_id,)).fetchone()
    if row is None:
        return _err(401, "Unauthorized", 401)
    return dict(row)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return str(uuid4())


def _str(body: dict[str, Any], *names: str) -> str:
    for name in names:
        value = body.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _query_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _json_params(value: Any) -> str:
    return json.dumps(value if isinstance(value, dict) else {}, ensure_ascii=False, sort_keys=True)


def _loads_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _device_access(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
    if account.get("role") == "admin":
        return True
    row = conn.execute(
        "SELECT 1 FROM v2_device_binding WHERE device_id=? AND account_id=? AND status='active'",
        (device_id, account["id"]),
    ).fetchone()
    return row is not None


def _require_device_access(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> JSONResponse | None:
    if not _device_access(conn, account, device_id):
        return _err(403, "Device is not bound to this account", 403)
    return None


def _device_payload(row: sqlite3.Row) -> dict[str, Any]:
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


def _task_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "taskId": row["id"],
        "id": row["id"],
        "deviceId": row["device_id"],
        "capability": row["intent"],
        "params": _loads_json(row["params"]),
        "source": row["source"],
        "status": row["status"],
        "progress": row["progress"],
        "errorMsg": row["error_msg"],
        "memberId": row["member_id"],
        "createdAt": row["created_at"],
        "startedAt": row["started_at"],
        "completedAt": row["completed_at"],
    }


def _member_payload(row: sqlite3.Row) -> dict[str, Any]:
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


def _voiceprint_payload(row: sqlite3.Row, member_name: str = "") -> dict[str, Any]:
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


def _transfer_payload(row: sqlite3.Row) -> dict[str, Any]:
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


def _supply_payload(row: sqlite3.Row) -> dict[str, Any]:
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


def _self_check_payload(row: sqlite3.Row) -> dict[str, Any]:
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


def _expires_at(seconds: int) -> str:
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=seconds))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _expire_pending_transfers(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE v2_device_transfer_request SET status='expired' WHERE status='pending' AND expires_at <= ?",
        (_now(),),
    )


def _is_owner(conn: sqlite3.Connection, account: dict[str, Any], device_id: str) -> bool:
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


def _parse_supply_updates(body: dict[str, Any]) -> tuple[list[dict[str, Any]], JSONResponse | None]:
    raw_items: list[dict[str, Any]] = []
    if isinstance(body.get("supplies"), list):
        raw_items.extend(item for item in body["supplies"] if isinstance(item, dict))
    direct_type = _str(body, "supplyType", "supply_type")
    if direct_type:
        raw_items.append(body)
    for supply_type in ("pen", "paper", "battery"):
        value = body.get(supply_type)
        if isinstance(value, dict):
            raw_items.append({"supplyType": supply_type, **value})
    updates: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        supply_type = _str(item, "supplyType", "supply_type")
        status = _str(item, "status") or "unknown"
        if not supply_type:
            return [], _err(400, "supplyType is required", 400)
        if status not in {"normal", "low", "empty", "unknown"}:
            return [], _err(400, "invalid supply status", 400)
        try:
            level = float(item.get("level", 1.0))
        except (TypeError, ValueError):
            return [], _err(400, "supply level must be numeric", 400)
        if not 0.0 <= level <= 1.0:
            return [], _err(400, "supply level must be between 0.0 and 1.0", 400)
        updates[supply_type] = {"supply_type": supply_type, "level": level, "status": status}
    if not updates:
        return [], _err(400, "at least one supply update is required", 400)
    return list(updates.values()), None


def _check_activation_code(code: str) -> bool:
    global _activation_warning_logged
    now = time.time()
    with _activation_lock:
        for saved_code, data in list(_activation_codes.items()):
            if data["expires_at"] <= now:
                _activation_codes.pop(saved_code, None)
        saved = _activation_codes.get(code)
        if saved and saved["expires_at"] > now:
            return True
    expected = os.environ.get("LIMA_XIAOZHI_ACTIVATION_CODE", "").strip()
    if expected:
        return secrets.compare_digest(code, expected)
    if not _activation_warning_logged:
        _log.warning("LIMA_XIAOZHI_ACTIVATION_CODE is not configured; accepting non-empty activation codes")
        _activation_warning_logged = True
    return bool(code)


def _new_activation_code(mac_address: str = "") -> str:
    now = time.time()
    with _activation_lock:
        for saved_code, data in list(_activation_codes.items()):
            if data["expires_at"] <= now:
                _activation_codes.pop(saved_code, None)
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in _activation_codes:
                break
        _activation_codes[code] = {"mac_address": mac_address, "expires_at": now + _ACTIVATION_TTL_SECONDS}
        return code


def _login_code() -> str:
    return os.environ.get("LIMA_XIAOZHI_LOGIN_CODE", "").strip() or "000000"


def _validate_login_code(code: str) -> bool:
    return secrets.compare_digest(code, _login_code())


def _login_response(row: sqlite3.Row) -> dict[str, Any] | JSONResponse:
    token = _make_token(row)
    if token is None:
        return _err(503, "JWT support is unavailable", 503)
    return {
        "token": token,
        "expiresIn": 86400,
        "accountId": row["id"],
        "phone": row["phone"],
    }


def _gateway_capability(intent: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
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


def _build_gateway_task(device_id: str, intent: str, params: dict[str, Any], source: str, request_id: str) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    capability, gateway_params, error = _gateway_capability(intent, params)
    if error:
        return None, _err(4001, error, 400)
    sanitized, validation_error = validate_capability_params(capability, gateway_params)
    if validation_error:
        return None, _err(4002, f"validation failed: {validation_error}", 400)
    policy = policy_engine.decide(capability=capability, device_id=device_id, fw_rev="", params=sanitized)
    if policy.decision != "allow":
        return None, _err(4003, policy.reason, 400)
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


async def _dispatch_or_enqueue(device_id: str, task: dict[str, Any]) -> dict[str, Any]:
    session = registry.get(device_id)
    sent = False
    if session is not None:
        sent = await dispatch_task_to_session(session, task)
    queue_depth = 0
    if not sent:
        queue_depth = enqueue_pending_task(device_id, task)
        await publish_task_available_safe(device_id, str(task.get("task_id", "")))
    return {"sent": sent, "queueDepth": queue_depth, "dispatchStatus": "sent" if sent else "queued"}


# ═══════════════════════ P0 Endpoints ═══════════════════════

@router.post("/login")
async def login(request: Request) -> JSONResponse:
    """手机号+验证码登录，自动注册新用户。"""
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = _str(body, "phone", "mobile")
    code = _str(body, "code", "smsCode")
    if not phone or not code:
        return _err(400, "phone and code are required", 400)
    if not _validate_login_code(code):
        return _err(401, "Invalid verification code", 401)
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE phone=? AND status='active'", (phone,)).fetchone()
        if row is None:
            account_id = _new_id()
            conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)", (account_id, phone, body.get("nickname")))
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return _ok(data)


@router.post("/auth/register")
async def register(request: Request) -> JSONResponse:
    """Register a phone account with the Phase 0 SMS verification code."""
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = _str(body, "phone", "mobile")
    code = _str(body, "code", "smsCode")
    if not phone or not code:
        return _err(400, "phone and code are required", 400)
    if not _validate_login_code(code):
        return _err(401, "Invalid verification code", 401)
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_account WHERE phone=? AND status='active'", (phone,)).fetchone()
        if row is None:
            account_id = _new_id()
            conn.execute(
                "INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
                (account_id, phone, body.get("nickname")),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM v2_account WHERE id=?", (account_id,)).fetchone()
    data = _login_response(row)
    if isinstance(data, JSONResponse):
        return data
    return _ok(data)


@router.post("/auth/sms-verification")
async def sms_verification(request: Request) -> JSONResponse:
    """Return the Phase 0 mock SMS code."""
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    phone = _str(body, "phone", "mobile")
    if not phone:
        return _err(400, "phone is required", 400)
    code = _login_code()
    return _ok({"phone": phone, "code": code, "mock": True, "expiresIn": 300})


@router.get("/auth/me")
async def get_me(authorization: str = Header(default="")) -> JSONResponse:
    """Return the current account from a JWT bearer token."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    return _ok(_account_payload(account))


@router.post("/auth/account/delete")
async def delete_account(authorization: str = Header(default="")) -> JSONResponse:
    """Soft-delete the current account and unbind its active devices."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    deleted_at = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE v2_device_binding
            SET status='unbound', unbound_at=?
            WHERE account_id=? AND status='active'
            """,
            (deleted_at, account["id"]),
        )
        conn.execute(
            """
            UPDATE v2_account
            SET status='deleted',
                deleted_at=?,
                nickname='deleted_user',
                phone=NULL,
                wechat_openid=NULL,
                avatar_url=NULL
            WHERE id=?
            """,
            (deleted_at, account["id"]),
        )
        conn.commit()
    return _ok({"accountId": account["id"], "deletedAt": deleted_at})


@router.post("/devices/register")
async def register_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Generate a short-lived Phase 0 activation code for device pairing."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    activation_code = _new_activation_code(_str(body, "macAddress", "mac_address"))
    return _ok({"activationCode": activation_code, "code": activation_code, "expiresIn": _ACTIVATION_TTL_SECONDS})


@router.post("/devices/bind")
async def bind_device(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """设备绑定：deviceSn + activationCode。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_sn = _str(body, "deviceSn", "device_sn")
    activation_code = _str(body, "activationCode", "activation_code")
    if not device_sn or not activation_code:
        return _err(400, "deviceSn and activationCode are required", 400)
    if not _check_activation_code(activation_code):
        return _err(4004, "Invalid activation code", 400)
    with _connect() as conn:
        owner = conn.execute(
            "SELECT account_id FROM v2_device_binding WHERE device_id=(SELECT id FROM v2_device WHERE device_sn=?) AND bind_mode='owner' AND status='active'",
            (device_sn,),
        ).fetchone()
        if owner is not None and owner["account_id"] != account["id"]:
            return _err(4005, "Device is already bound", 400)
        device = conn.execute("SELECT * FROM v2_device WHERE device_sn=?", (device_sn,)).fetchone()
        if device is None:
            device_id = _new_id()
            conn.execute(
                "INSERT INTO v2_device (id, device_sn, model, metadata) VALUES (?, ?, ?, ?)",
                (device_id, device_sn, _str(body, "model") or "esp32s3_xyz", _json_params(body.get("metadata"))),
            )
            device = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
        binding = conn.execute(
            "SELECT * FROM v2_device_binding WHERE device_id=? AND account_id=?",
            (device["id"], account["id"]),
        ).fetchone()
        if binding is None:
            binding_id = _new_id()
            conn.execute(
                "INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')",
                (binding_id, device["id"], account["id"]),
            )
        else:
            binding_id = binding["id"]
            conn.execute("UPDATE v2_device_binding SET status='active', unbound_at=NULL WHERE id=?", (binding_id,))
        conn.commit()
    return _ok({"bindingId": binding_id, "deviceId": device["id"], "device": _device_payload(device)})


@router.get("/devices")
async def list_devices(authorization: str = Header(default="")) -> JSONResponse:
    """List devices actively bound to the current account."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        if account.get("role") == "admin":
            rows = conn.execute("SELECT * FROM v2_device ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute(
                """
                SELECT d.*
                FROM v2_device d
                JOIN v2_device_binding b ON b.device_id = d.id
                WHERE b.account_id=? AND b.status='active'
                ORDER BY b.bound_at DESC
                """,
                (account["id"],),
            ).fetchall()
    return _ok([_device_payload(row) for row in rows])


@router.get("/devices/{device_id}")
async def get_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Return a bound device detail."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    if row is None:
        return _err(404, "device not found", 404)
    return _ok(_device_payload(row))


@router.put("/devices/{device_id}")
async def update_device(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """Update mutable device profile fields."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    updates: dict[str, Any] = {}
    for body_name, column_name in (
        ("model", "model"),
        ("firmwareVer", "firmware_ver"),
        ("firmware_ver", "firmware_ver"),
        ("hardwareVer", "hardware_ver"),
        ("hardware_ver", "hardware_ver"),
    ):
        value = body.get(body_name)
        if isinstance(value, str) and value.strip():
            updates[column_name] = value.strip()
    if "metadata" in body:
        if isinstance(body["metadata"], dict):
            updates["metadata"] = _json_params(body["metadata"])
        elif isinstance(body["metadata"], str):
            updates["metadata"] = body["metadata"]
        else:
            return _err(400, "metadata must be an object or string", 400)
    if not updates:
        return _err(400, "no supported device fields provided", 400)
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        assignments = ", ".join(f"{column}=?" for column in updates)
        result = conn.execute(
            f"UPDATE v2_device SET {assignments} WHERE id=?",
            (*updates.values(), device_id),
        )
        conn.commit()
        if result.rowcount < 1:
            return _err(404, "device not found", 404)
        row = conn.execute("SELECT * FROM v2_device WHERE id=?", (device_id,)).fetchone()
    return _ok(_device_payload(row))


@router.post("/devices/{device_id}/unbind")
async def unbind_device(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Mark the current account's active device binding as unbound."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        if account.get("role") == "admin":
            result = conn.execute(
                "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND status='active'",
                (_now(), device_id),
            )
        else:
            result = conn.execute(
                "UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND account_id=? AND status='active'",
                (_now(), device_id, account["id"]),
            )
        conn.commit()
    if result.rowcount < 1:
        return _err(404, "active binding not found", 404)
    return _ok({"deviceId": device_id, "status": "unbound"})


@router.post("/devices/{device_id}/tasks")
async def submit_task(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """提交运动任务。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    intent = _str(body, "capability", "intent")
    if intent not in _ALLOWED_TASKS:
        return _err(4001, "unsupported capability", 400)
    source = _str(body, "source") or "api"
    if source not in _ALLOWED_SOURCES:
        return _err(400, "invalid source", 400)
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    member_id = _str(body, "memberId", "member_id") or None
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        if member_id:
            member = conn.execute("SELECT 1 FROM v2_member WHERE id=? AND device_id=? AND status='active'", (member_id, device_id)).fetchone()
            if member is None:
                return _err(404, "member not found", 404)
        task, error = _build_gateway_task(device_id, intent, params, source, _str(body, "requestId", "request_id"))
        if error:
            return error
        status = "pending" if task["workflow_state"] == TaskState.WAITING_APPROVAL.value else "approved"
        conn.execute(
            "INSERT INTO v2_task (id, device_id, account_id, member_id, intent, params, source, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (task["task_id"], device_id, account["id"], member_id, intent, _json_params(params), source, status),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task["task_id"],)).fetchone()
    dispatch = {"sent": False, "queueDepth": 0, "dispatchStatus": "waiting_approval"}
    if status == "approved":
        dispatch = await _dispatch_or_enqueue(device_id, task)
    data = _task_payload(row)
    data.update(dispatch)
    return _ok(data)


@router.get("/devices/{device_id}/tasks")
async def list_tasks(
    device_id: str,
    request: Request,
    authorization: str = Header(default=""),
) -> JSONResponse:
    """List tasks for a bound device."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    status = str(request.query_params.get("status") or "").strip()
    if status and status not in _ALLOWED_TASK_STATUSES:
        return _err(400, "invalid task status", 400)
    limit = _query_int(request.query_params.get("limit"), default=20, minimum=1, maximum=100)
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        if status:
            rows = conn.execute(
                "SELECT * FROM v2_task WHERE device_id=? AND status=? ORDER BY created_at DESC LIMIT ?",
                (device_id, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM v2_task WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
    return _ok([_task_payload(row) for row in rows])


# ═══════════════════════ P1 Endpoints ═══════════════════════


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """Return a task detail if the current account can access the device."""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return _err(404, "task not found", 404)
        denied = _require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
    return _ok(_task_payload(row))


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """审批任务并下发。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return _err(404, "task not found", 404)
        denied = _require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute("UPDATE v2_task SET status='approved' WHERE id=? AND status='pending'", (task_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
    snapshot = task_snapshot(task_id) or {}
    task = snapshot.get("task") if isinstance(snapshot.get("task"), dict) else None
    dispatch = {"sent": False, "queueDepth": 0, "dispatchStatus": "not_dispatched"}
    if task is not None:
        try:
            if workflow.get_state(task_id) == TaskState.WAITING_APPROVAL:
                workflow.advance(task_id, TaskState.READY_TO_DISPATCH)
                task["workflow_state"] = TaskState.READY_TO_DISPATCH.value
        except WorkflowTransitionError as exc:
            _log.warning("approve workflow transition skipped task=%s err=%s", task_id, exc)
        dispatch = await _dispatch_or_enqueue(row["device_id"], task)
    data = _task_payload(row)
    data.update(dispatch)
    return _ok(data)


@router.post("/tasks/{task_id}/reject")
async def reject_task(task_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """拒绝任务。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    reason = _str(body, "reason", "comment") or "rejected"
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return _err(404, "task not found", 404)
        denied = _require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute("UPDATE v2_task SET status='rejected', error_msg=?, completed_at=? WHERE id=?", (reason, _now(), task_id))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_task WHERE id=?", (task_id,)).fetchone()
    record_motion_event({"type": "motion_event", "device_id": row["device_id"], "task_id": task_id, "phase": "rejected", "error": {"code": "E_REJECTED", "reason": reason}})
    try:
        if workflow.get_state(task_id) == TaskState.WAITING_APPROVAL:
            workflow.advance(task_id, TaskState.TERMINAL)
    except WorkflowTransitionError as exc:
        _log.warning("reject workflow transition skipped task=%s err=%s", task_id, exc)
    return _ok(_task_payload(row))


@router.get("/devices/{device_id}/tasks/pending")
async def pending_tasks(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """列出待审批任务。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute("SELECT * FROM v2_task WHERE device_id=? AND status='pending' ORDER BY created_at DESC", (device_id,)).fetchall()
    return _ok([_task_payload(row) for row in rows])


@router.post("/voiceprints/enroll")
async def enroll_voiceprint(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """声纹注册。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    member_id = _str(body, "memberId", "member_id")
    device_id = _str(body, "deviceId", "device_id")
    if not member_id or not device_id:
        return _err(400, "memberId and deviceId are required", 400)
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        member = conn.execute("SELECT * FROM v2_member WHERE id=? AND device_id=? AND status='active'", (member_id, device_id)).fetchone()
        if member is None:
            return _err(404, "member not found", 404)
        row = conn.execute("SELECT * FROM v2_voiceprint WHERE member_id=? AND device_id=? AND status!='disabled'", (member_id, device_id)).fetchone()
        if row is None:
            voiceprint_id = _new_id()
            conn.execute("INSERT INTO v2_voiceprint (id, member_id, device_id, status) VALUES (?, ?, ?, 'verifying')", (voiceprint_id, member_id, device_id))
            conn.execute("UPDATE v2_member SET voiceprint_id=? WHERE id=?", (voiceprint_id, member_id))
            conn.commit()
            row = conn.execute("SELECT * FROM v2_voiceprint WHERE id=?", (voiceprint_id,)).fetchone()
    return _ok(_voiceprint_payload(row, member["name"]))


@router.post("/members")
async def create_member(request: Request, authorization: str = Header(default="")) -> JSONResponse:
    """创建家庭成员。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    device_id = _str(body, "deviceId", "device_id")
    name = _str(body, "name")
    role = _str(body, "role") or "child"
    if not device_id or not name:
        return _err(400, "deviceId and name are required", 400)
    if role not in _ALLOWED_MEMBER_ROLES:
        return _err(400, "invalid member role", 400)
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        member_id = _new_id()
        conn.execute(
            "INSERT INTO v2_member (id, account_id, device_id, name, role, avatar_url) VALUES (?, ?, ?, ?, ?, ?)",
            (member_id, account["id"], device_id, name, role, body.get("avatarUrl") or body.get("avatar_url")),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_member WHERE id=?", (member_id,)).fetchone()
    return _ok(_member_payload(row))


@router.get("/devices/{device_id}/members")
async def list_members(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    """列出设备上的家庭成员。"""
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute("SELECT * FROM v2_member WHERE device_id=? AND status='active' ORDER BY created_at ASC", (device_id,)).fetchall()
    return _ok([_member_payload(row) for row in rows])

@router.delete("/voiceprints/{voiceprint_id}")
async def delete_voiceprint(voiceprint_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        row = conn.execute("SELECT * FROM v2_voiceprint WHERE id=? AND status!='disabled'", (voiceprint_id,)).fetchone()
        if row is None:
            return _err(404, "voiceprint not found", 404)
        denied = _require_device_access(conn, account, row["device_id"])
        if denied:
            return denied
        conn.execute("UPDATE v2_voiceprint SET status='disabled' WHERE id=?", (voiceprint_id,))
        conn.execute("UPDATE v2_member SET voiceprint_id=NULL WHERE voiceprint_id=?", (voiceprint_id,))
        conn.commit()
    return _ok({"voiceprintId": voiceprint_id, "status": "disabled"})


@router.post("/devices/{device_id}/transfer")
async def request_transfer(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    to_phone = _str(body, "toPhone", "to_phone")
    to_account_id = _str(body, "toAccountId", "to_account_id")
    reason = _str(body, "reason") or ""
    with _connect() as conn:
        if not _is_owner(conn, account, device_id):
            return _err(403, "only the device owner can initiate a transfer", 403)
        _expire_pending_transfers(conn)
        if to_phone:
            target = conn.execute("SELECT id FROM v2_account WHERE phone=? AND status='active'", (to_phone,)).fetchone()
            if target is None:
                return _err(404, "recipient account not found", 404)
            to_account_id = target["id"]
        if not to_account_id:
            return _err(400, "toPhone or toAccountId is required", 400)
        if to_account_id == account["id"]:
            return _err(400, "cannot transfer to yourself", 400)
        transfer_id = _new_id()
        conn.execute(
            "INSERT INTO v2_device_transfer_request (id, device_id, from_account_id, to_account_id, status, reason, expires_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (transfer_id, device_id, account["id"], to_account_id, reason, _expires_at(172800)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return _ok(_transfer_payload(row))


@router.get("/transfers/pending")
async def list_pending_transfers(authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        _expire_pending_transfers(conn)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM v2_device_transfer_request WHERE to_account_id=? AND status='pending' ORDER BY created_at DESC",
            (account["id"],),
        ).fetchall()
    return _ok([_transfer_payload(row) for row in rows])


@router.post("/transfers/{transfer_id}/accept")
async def accept_transfer(transfer_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        _expire_pending_transfers(conn)
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=? AND status='pending'", (transfer_id,)).fetchone()
        if row is None:
            return _err(404, "pending transfer not found or expired", 404)
        if row["to_account_id"] != account["id"]:
            return _err(403, "only the recipient can accept this transfer", 403)
        conn.execute("UPDATE v2_device_binding SET status='unbound', unbound_at=? WHERE device_id=? AND bind_mode='owner' AND status='active'", (_now(), row["device_id"]))
        existing = conn.execute("SELECT id FROM v2_device_binding WHERE device_id=? AND account_id=?", (row["device_id"], account["id"])).fetchone()
        if existing:
            conn.execute("UPDATE v2_device_binding SET status='active', bind_mode='owner', unbound_at=NULL WHERE id=?", (existing["id"],))
        else:
            conn.execute("INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status) VALUES (?, ?, ?, 'owner', 'active')", (_new_id(), row["device_id"], account["id"]))
        conn.execute("UPDATE v2_device_transfer_request SET status='accepted', accepted_at=? WHERE id=?", (_now(), transfer_id))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return _ok(_transfer_payload(row))


@router.post("/transfers/{transfer_id}/cancel")
async def cancel_transfer(transfer_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        _expire_pending_transfers(conn)
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=? AND status='pending'", (transfer_id,)).fetchone()
        if row is None:
            return _err(404, "pending transfer not found or expired", 404)
        if row["from_account_id"] != account["id"] and account.get("role") != "admin":
            return _err(403, "only the initiator or an admin can cancel", 403)
        conn.execute("UPDATE v2_device_transfer_request SET status='cancelled', cancelled_at=? WHERE id=?", (_now(), transfer_id))
        conn.commit()
        row = conn.execute("SELECT * FROM v2_device_transfer_request WHERE id=?", (transfer_id,)).fetchone()
    return _ok(_transfer_payload(row))


@router.get("/devices/{device_id}/self-checks")
async def list_self_checks(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    limit = _query_int(request.query_params.get("limit"), default=20, minimum=1, maximum=100)
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute("SELECT * FROM v2_self_check_event WHERE device_id=? ORDER BY created_at DESC LIMIT ?", (device_id, limit)).fetchall()
    return _ok([_self_check_payload(row) for row in rows])


@router.put("/devices/{device_id}/supplies")
async def update_supplies(device_id: str, request: Request, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    body = await _read_body(request)
    if isinstance(body, JSONResponse):
        return body
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
    items, error = _parse_supply_updates(body)
    if error:
        return error
    with _connect() as conn:
        for item in items:
            conn.execute(
                "INSERT INTO v2_device_supply (id, device_id, supply_type, level, status) VALUES (?, ?, ?, ?, ?) ON CONFLICT(device_id, supply_type) DO UPDATE SET level=?, status=?, updated_at=?",
                (_new_id(), device_id, item["supply_type"], item["level"], item["status"], item["level"], item["status"], _now()),
            )
        conn.commit()
        rows = conn.execute("SELECT * FROM v2_device_supply WHERE device_id=? ORDER BY supply_type", (device_id,)).fetchall()
    return _ok([_supply_payload(row) for row in rows])


@router.get("/devices/{device_id}/supplies")
async def get_supplies(device_id: str, authorization: str = Header(default="")) -> JSONResponse:
    account = _authorize(authorization)
    if isinstance(account, JSONResponse):
        return account
    with _connect() as conn:
        denied = _require_device_access(conn, account, device_id)
        if denied:
            return denied
        rows = conn.execute("SELECT * FROM v2_device_supply WHERE device_id=? ORDER BY supply_type", (device_id,)).fetchall()
    return _ok([_supply_payload(row) for row in rows])
