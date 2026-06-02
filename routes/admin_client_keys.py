"""Client API Key management for LiMa admin panel.

Provides CRUD endpoints for managing distributed client API keys,
including quota configuration, usage tracking, and URL restrictions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routes.admin_auth import verify_admin, verify_csrf

router = APIRouter()
_log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_KEYS_PATH = _DATA_DIR / "client_keys.json"
_lock = threading.Lock()

# ── Daily/monthly quota + RPM tracking (in-memory, resets on restart) ──────

_usage: dict[str, dict] = {}  # key_value -> {daily_count, monthly_count, day, month, rpm_timestamps}
_rpm_window: dict[str, list[float]] = {}  # key_value -> [timestamps within 60s window]


def _now_day() -> str:
    return time.strftime("%Y-%m-%d")


def _now_month() -> str:
    return time.strftime("%Y-%m")


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


def check_allowed_urls(key_record: dict, request_path: str) -> bool:
    """Return True if request_path is within the key's allowed_urls whitelist."""
    allowed = key_record.get("allowed_urls", ["*"])
    if not allowed or "*" in allowed:
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
    """Atomically check ALL quotas (daily, monthly, RPM) and record usage.

    Returns (allowed, reason) where reason is empty on success or a short
    description like 'daily_limit', 'monthly_limit', 'rpm_limit' on denial.
    This replaces the old separate check_key_quota + record_key_usage pair
    to eliminate the TOCTOU race condition.
    """
    token = key_record["key_value"]
    daily_limit = key_record.get("quota_daily", 0)
    monthly_limit = key_record.get("quota_monthly", 0)
    rpm_limit = key_record.get("rate_limit_rpm", 0)
    now = time.time()
    day = _now_day()
    month = _now_month()
    window_start = now - 60.0

    with _lock:
        entry = _usage.setdefault(token, {
            "day": day, "month": month,
            "daily_count": 0, "monthly_count": 0,
            "last_used_at": None,
        })
        # Reset counters on day/month rollover
        if entry.get("day") != day:
            entry["day"] = day
            entry["daily_count"] = 0
        if entry.get("month") != month:
            entry["month"] = month
            entry["monthly_count"] = 0

        # Daily quota check
        if daily_limit > 0 and entry["daily_count"] >= daily_limit:
            return False, "daily_limit"

        # Monthly quota check
        if monthly_limit > 0 and entry["monthly_count"] >= monthly_limit:
            return False, "monthly_limit"

        # RPM (requests per minute) sliding window check
        if rpm_limit > 0:
            timestamps = _rpm_window.setdefault(token, [])
            # Prune expired entries outside the 60s window
            timestamps[:] = [t for t in timestamps if t > window_start]
            if len(timestamps) >= rpm_limit:
                return False, "rpm_limit"
            timestamps.append(now)

        # All checks passed — consume the quota
        entry["daily_count"] += 1
        entry["monthly_count"] += 1
        entry["last_used_at"] = now

    # Persist usage counters to key record (throttled: every 10 requests)
    if entry["daily_count"] % 10 == 0:
        _persist_usage(token, entry)
    return True, ""


# ── Legacy API (backward compatible with tests and callers) ────────────────


def check_key_quota(key_record: dict) -> bool:
    """Check if key has remaining quota WITHOUT consuming it (read-only)."""
    if not key_record.get("enabled", False):
        return False
    token = key_record["key_value"]
    daily_limit = key_record.get("quota_daily", 0)
    monthly_limit = key_record.get("quota_monthly", 0)
    day = _now_day()
    month = _now_month()
    with _lock:
        entry = _usage.get(token)
        if entry is None:
            return True  # never used, definitely has quota
        # Reset counters on day/month rollover
        if entry.get("day") != day:
            entry["day"] = day
            entry["daily_count"] = 0
        if entry.get("month") != month:
            entry["month"] = month
            entry["monthly_count"] = 0
        if daily_limit > 0 and entry["daily_count"] >= daily_limit:
            return False
        if monthly_limit > 0 and entry["monthly_count"] >= monthly_limit:
            return False
    return True


def record_key_usage(token: str) -> None:
    """Increment request count for a client key (legacy, use try_consume_quota instead)."""
    now = time.time()
    day = _now_day()
    month = _now_month()
    with _lock:
        entry = _usage.setdefault(token, {
            "day": day, "month": month,
            "daily_count": 0, "monthly_count": 0,
            "last_used_at": None,
        })
        if entry.get("day") != day:
            entry["day"] = day
            entry["daily_count"] = 0
        if entry.get("month") != month:
            entry["month"] = month
            entry["monthly_count"] = 0
        entry["daily_count"] += 1
        entry["monthly_count"] += 1
        entry["last_used_at"] = now
    # Persist usage counters to key record (throttled: every 10 requests)
    if entry["daily_count"] % 10 == 0:
        _persist_usage(token, entry)


def _persist_usage(token: str, usage_entry: dict) -> None:
    """Write usage counters back to the key store file."""
    with _lock:
        keys = _load_keys()
        for key in keys:
            if key.get("key_value") == token:
                key["request_count"] = usage_entry.get("monthly_count", 0)
                key["last_used_at"] = usage_entry.get("last_used_at")
                _save_keys(keys)
                break


def get_key_usage_summary(token: str) -> dict:
    """Get current usage summary for a key."""
    entry = _usage.get(token, {})
    return {
        "daily_count": entry.get("daily_count", 0),
        "monthly_count": entry.get("monthly_count", 0),
        "last_used_at": entry.get("last_used_at"),
    }


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
        result.append({
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
        })
    return {"keys": result, "total": len(result)}


@router.post("/admin/api/client-keys", dependencies=[Depends(verify_admin), Depends(verify_csrf)])
async def create_client_key(body: dict):
    """Issue a new client API key."""
    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(400, "label is required")

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
        "quota_daily": int(body.get("quota_daily", 1000)),
        "quota_monthly": int(body.get("quota_monthly", 30000)),
        "rate_limit_rpm": int(body.get("rate_limit_rpm", 20)),
        "allowed_urls": body.get("allowed_urls", ["*"]),
    }
    with _lock:
        keys = _load_keys()
        keys.append(key_record)
        _save_keys(keys)

    _log.info("admin: created client key %s label=%s", key_record["key_id"], label)
    return {
        "ok": True,
        "key_id": key_record["key_id"],
        "key_value": token,
        "label": label,
    }


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
                    key["quota_daily"] = int(body["quota_daily"])
                if "quota_monthly" in body:
                    key["quota_monthly"] = int(body["quota_monthly"])
                if "rate_limit_rpm" in body:
                    key["rate_limit_rpm"] = int(body["rate_limit_rpm"])
                if "allowed_urls" in body:
                    key["allowed_urls"] = body["allowed_urls"]
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
async def regenerate_client_key(key_id: str):
    """Regenerate the key value for an existing key record."""
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
                _usage.pop(old_token, None)
                _rpm_window.pop(old_token, None)
                _log.info("admin: regenerated client key %s", key_id)
                return {
                    "ok": True,
                    "key_id": key_id,
                    "key_value": new_token,
                }
    raise HTTPException(404, f"Key '{key_id}' not found")
