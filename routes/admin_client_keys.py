"""Client API Key management for LiMa admin panel.

Provides CRUD endpoints for managing distributed client API keys,
including quota configuration, usage tracking, and URL restrictions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf
from routes.client_key_quota import QuotaTracker

router = APIRouter()
_log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KEYS_PATH = _DATA_DIR / "client_keys.json"
_lock = threading.Lock()

# Quota/RPM tracker; mutable state is encapsulated so tests can replace it.
_tracker = QuotaTracker(_KEYS_PATH)


# ── Storage helpers ─────────────────────────────────────────────────────────


def _load_keys() -> list[dict]:
    if not _KEYS_PATH.exists():
        return []
    try:
        data = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
        return data.get("keys", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_keys(keys: list[dict]) -> None:
    """Atomically persist keys to disk (write-tmp-then-rename)."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _KEYS_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"keys": keys}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(_KEYS_PATH)  # atomic on POSIX, near-atomic on Windows


def has_client_keys() -> bool:
    """Return True if the client key store exists and contains at least one key."""
    if not _KEYS_PATH.exists():
        return False
    try:
        data = json.loads(_KEYS_PATH.read_text(encoding="utf-8"))
        keys = data.get("keys", []) if isinstance(data, dict) else []
        return bool(keys)
    except (json.JSONDecodeError, OSError):
        return False


def _generate_key_value() -> str:
    """Generate a random API key with lima- prefix."""
    random_part = secrets.token_hex(16)
    return f"lima-{random_part[:8]}-{random_part[8:16]}-{random_part[16:]}"


def _mask_key(value: str) -> str:
    """Mask key for display: show prefix + last 4 chars."""
    if not value:
        return ""
    if len(value) <= 12:
        return value[:5] + "****"
    return value[:10] + "****" + value[-4:]


def _key_id(value: str) -> str:
    """Generate a stable key_id from key value."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    suffix = value[-4:] if len(value) >= 4 else value
    return f"ck-{digest}-{suffix}"


def _normalize_allowed_urls(value: object) -> list[str]:
    """Validate and normalize an allowed_urls value.

    Raises HTTPException(400) if the value is not a list of strings.
    """
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="allowed_urls must be a list of strings")
    for item in value:
        if not isinstance(item, str):
            raise HTTPException(status_code=400, detail="allowed_urls must be a list of strings")
    return value


def _normalize_quota(value: object, field: str) -> int:
    """Validate a quota/limit field and return a non-negative int.

    Raises HTTPException(400) on malformed or negative values.
    """
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be an integer") from exc
    if number < 0:
        raise HTTPException(status_code=400, detail=f"{field} must be non-negative")
    return number


def check_allowed_urls(key_record: dict, request_path: str) -> bool:
    """Return True if request_path is within the key's allowed_urls whitelist.

    Semantics:
      - Missing field defaults to ["*"] (allow all).
      - Explicit empty list or None denies all access.
      - "*" anywhere in the list allows all.
      - Otherwise the request path must match an entry exactly.
    """
    allowed = key_record.get("allowed_urls", ["*"])
    if allowed is None or allowed == []:
        return False
    if "*" in allowed:
        return True
    return request_path in allowed


# ── Public API for access_guard integration ─────────────────────────────────


def find_client_key(token: str) -> dict | None:
    """Look up a client key by its raw value. Returns the key record or None."""
    with _lock:
        for key in _load_keys():
            if key.get("key_value") == token:
                return key
    return None


def try_consume_quota(key_record: dict) -> tuple[bool, str]:
    """Atomically check ALL quotas (daily, monthly, RPM) and record usage."""
    return _tracker.try_consume_quota(key_record)


def check_key_quota(key_record: dict) -> bool:
    """Check if key has remaining quota WITHOUT consuming it (read-only)."""
    return _tracker.check_key_quota(key_record)


def record_key_usage(token: str) -> None:
    """Increment request count for a client key (legacy, use try_consume_quota instead)."""
    _tracker.record_usage(token)


def get_key_usage_summary(token: str) -> dict:
    """Get current usage summary for a key."""
    return _tracker.usage_summary(token)


# ── Admin API endpoints ─────────────────────────────────────────────────────


@router.get("/admin/api/client-keys", dependencies=[Depends(verify_admin)])
async def list_client_keys():
    """List all client keys with masked values and usage stats."""
    with _lock:
        keys = _load_keys()
    result = []
    for k in keys:
        token = k.get("key_value", "")
        usage = get_key_usage_summary(token)
        result.append(
            {
                "key_id": k.get("key_id", ""),
                "key_masked": _mask_key(token),
                "label": k.get("label", ""),
                "enabled": k.get("enabled", True),
                "created_at": k.get("created_at", 0),
                "last_used_at": usage.get("last_used_at") or k.get("last_used_at"),
                "request_count": k.get("request_count", 0),
                "quota_daily": k.get("quota_daily", 1000),
                "quota_monthly": k.get("quota_monthly", 30000),
                "rate_limit_rpm": k.get("rate_limit_rpm", 20),
                "allowed_urls": k.get("allowed_urls", ["*"]),
                "usage_daily": usage.get("daily_count", 0),
                "usage_monthly": usage.get("monthly_count", 0),
            }
        )
    return {"keys": result, "total": len(result)}


@router.post("/admin/api/client-keys", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_client_key(body: dict):
    """Issue a new client API key.

    The raw key_value is only returned when body["reveal"] is truthy; otherwise
    only the masked value is returned to avoid leaking secrets in logs/UI.
    """
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "label is required")

    allowed_urls = body.get("allowed_urls", ["*"])
    allowed_urls = _normalize_allowed_urls(allowed_urls)

    token = _generate_key_value()
    now = time.time()
    key_record = {
        "key_id": _key_id(token),
        "key_value": token,
        "label": label,
        "enabled": True,
        "created_at": now,
        "last_used_at": None,
        "request_count": 0,
        "quota_daily": _normalize_quota(body.get("quota_daily", 1000), "quota_daily"),
        "quota_monthly": _normalize_quota(body.get("quota_monthly", 30000), "quota_monthly"),
        "rate_limit_rpm": _normalize_quota(body.get("rate_limit_rpm", 20), "rate_limit_rpm"),
        "allowed_urls": allowed_urls,
    }
    with _lock:
        keys = _load_keys()
        keys.append(key_record)
        _save_keys(keys)

    _log.info("admin: created client key %s label=%s", key_record["key_id"], label)
    result: dict = {
        "ok": True,
        "key_id": key_record["key_id"],
        "key_masked": _mask_key(token),
        "label": label,
    }
    if body.get("reveal"):
        _log.warning("admin: revealing raw key_value for %s", key_record["key_id"])
        result["key_value"] = token
    return result


@router.put("/admin/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def update_client_key(key_id: str, body: dict):
    """Update client key configuration (label, quota, URLs, enabled)."""
    with _lock:
        keys = _load_keys()
        for key in keys:
            if key.get("key_id") == key_id:
                if "label" in body:
                    key["label"] = body["label"]
                if "enabled" in body:
                    key["enabled"] = bool(body["enabled"])
                if "quota_daily" in body:
                    key["quota_daily"] = _normalize_quota(body["quota_daily"], "quota_daily")
                if "quota_monthly" in body:
                    key["quota_monthly"] = _normalize_quota(body["quota_monthly"], "quota_monthly")
                if "rate_limit_rpm" in body:
                    key["rate_limit_rpm"] = _normalize_quota(body["rate_limit_rpm"], "rate_limit_rpm")
                if "allowed_urls" in body:
                    key["allowed_urls"] = _normalize_allowed_urls(body["allowed_urls"])
                _save_keys(keys)
                _log.info("admin: updated client key %s", key_id)
                return {"ok": True, "key_id": key_id}
    raise HTTPException(404, f"Key '{key_id}' not found")


@router.delete("/admin/api/client-keys/{key_id}", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def delete_client_key(key_id: str):
    """Delete/revoke a client API key."""
    with _lock:
        keys = _load_keys()
        new_keys = [k for k in keys if k.get("key_id") != key_id]
        if len(new_keys) == len(keys):
            raise HTTPException(404, f"Key '{key_id}' not found")
        _save_keys(new_keys)
    _log.info("admin: deleted client key %s", key_id)
    return {"ok": True, "deleted": key_id}


@router.post("/admin/api/client-keys/{key_id}/regenerate", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def regenerate_client_key(key_id: str, body: dict | None = None):
    """Regenerate the key value for an existing key record.

    The raw key_value is only returned when body["reveal"] is truthy.
    """
    body = body or {}
    new_token = _generate_key_value()
    with _lock:
        keys = _load_keys()
        for key in keys:
            if key.get("key_id") == key_id:
                old_token = key.get("key_value", "")
                key["key_value"] = new_token
                # key_id stays the same — preserve external references
                key["request_count"] = 0
                key["last_used_at"] = None
                _save_keys(keys)
                # Clean up old usage entry
                _tracker.clear_token(old_token)
                _log.info("admin: regenerated client key %s", key_id)
                result: dict = {
                    "ok": True,
                    "key_id": key_id,
                    "key_masked": _mask_key(new_token),
                }
                if body.get("reveal"):
                    _log.warning("admin: revealing raw key_value for %s", key_id)
                    result["key_value"] = new_token
                return result
    raise HTTPException(404, f"Key '{key_id}' not found")
