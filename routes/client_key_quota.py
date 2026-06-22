"""In-memory quota/RPM tracker for client API keys.

This module isolates the mutable per-process usage state used by client-key
quota enforcement. It is intentionally pluggable so that a shared backend
(e.g. Redis) can be introduced later without changing callers.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

_log = logging.getLogger(__name__)


def _now_day() -> str:
    return time.strftime("%Y-%m-%d")


def _now_month() -> str:
    return time.strftime("%Y-%m")


class QuotaTracker:
    """Track daily/monthly quota and RPM limits for client API keys.

    State is kept in memory and reset on process restart. Persistence of usage
    counters back to the key store is throttled (every 10 requests).
    """

    def __init__(self, keys_path: Path | None = None) -> None:
        self._keys_path = keys_path
        self._lock = threading.Lock()
        self._usage: dict[str, dict] = {}
        self._rpm_window: dict[str, list[float]] = {}

    def _load_keys(self) -> list[dict]:
        if not self._keys_path or not self._keys_path.exists():
            return []
        try:
            data = json.loads(self._keys_path.read_text(encoding="utf-8"))
            return data.get("keys", []) if isinstance(data, dict) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_keys(self, keys: list[dict]) -> None:
        if not self._keys_path:
            return
        self._keys_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._keys_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"keys": keys}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self._keys_path)

    def _persist_usage(self, token: str, usage_entry: dict) -> None:
        """Write usage counters back to the key store file."""
        with self._lock:
            keys = self._load_keys()
            for key in keys:
                if key.get("key_value") == token:
                    key["request_count"] = usage_entry.get("monthly_count", 0)
                    key["last_used_at"] = usage_entry.get("last_used_at")
                    self._save_keys(keys)
                    break

    def usage_summary(self, token: str) -> dict:
        """Get current usage summary for a key."""
        entry = self._usage.get(token, {})
        return {
            "daily_count": entry.get("daily_count", 0),
            "monthly_count": entry.get("monthly_count", 0),
            "last_used_at": entry.get("last_used_at"),
        }

    def clear_token(self, token: str) -> None:
        """Drop in-memory usage state for a token (e.g. after regeneration)."""
        self._usage.pop(token, None)
        self._rpm_window.pop(token, None)

    def check_key_quota(self, key_record: dict) -> bool:
        """Check if key has remaining quota WITHOUT consuming it (read-only)."""
        if not key_record.get("enabled", False):
            return False
        token = key_record["key_value"]
        daily_limit = key_record.get("quota_daily", 0)
        monthly_limit = key_record.get("quota_monthly", 0)
        day = _now_day()
        month = _now_month()
        with self._lock:
            entry = self._usage.get(token)
            if entry is None:
                return True
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

    def record_usage(self, token: str) -> None:
        """Increment request count for a client key (legacy API)."""
        now = time.time()
        day = _now_day()
        month = _now_month()
        with self._lock:
            entry = self._usage.setdefault(
                token,
                {
                    "day": day,
                    "month": month,
                    "daily_count": 0,
                    "monthly_count": 0,
                    "last_used_at": None,
                },
            )
            if entry.get("day") != day:
                entry["day"] = day
                entry["daily_count"] = 0
            if entry.get("month") != month:
                entry["month"] = month
                entry["monthly_count"] = 0
            entry["daily_count"] += 1
            entry["monthly_count"] += 1
            entry["last_used_at"] = now
        if entry["daily_count"] % 10 == 0:
            self._persist_usage(token, entry)

    def try_consume_quota(self, key_record: dict) -> tuple[bool, str]:
        """Atomically check ALL quotas and record usage.

        Returns (allowed, reason). Reason is empty on success or one of
        'daily_limit', 'monthly_limit', 'rpm_limit' on denial.
        """
        token = key_record["key_value"]
        daily_limit = key_record.get("quota_daily", 0)
        monthly_limit = key_record.get("quota_monthly", 0)
        rpm_limit = key_record.get("rate_limit_rpm", 0)
        now = time.time()
        day = _now_day()
        month = _now_month()

        with self._lock:
            entry = self._usage.setdefault(
                token,
                {
                    "day": day,
                    "month": month,
                    "daily_count": 0,
                    "monthly_count": 0,
                    "last_used_at": None,
                },
            )
            self._reset_rollover(entry, day, month)

            if daily_limit > 0 and entry["daily_count"] >= daily_limit:
                return False, "daily_limit"
            if monthly_limit > 0 and entry["monthly_count"] >= monthly_limit:
                return False, "monthly_limit"
            if rpm_limit > 0 and self._rpm_exceeded(token, rpm_limit, now):
                return False, "rpm_limit"

            entry["daily_count"] += 1
            entry["monthly_count"] += 1
            entry["last_used_at"] = now

        if entry["daily_count"] % 10 == 0:
            self._persist_usage(token, entry)
        return True, ""

    def _reset_rollover(self, entry: dict, day: str, month: str) -> None:
        if entry.get("day") != day:
            entry["day"] = day
            entry["daily_count"] = 0
        if entry.get("month") != month:
            entry["month"] = month
            entry["monthly_count"] = 0

    def _rpm_exceeded(self, token: str, rpm_limit: int, now: float) -> bool:
        window_start = now - 60.0
        timestamps = self._rpm_window.setdefault(token, [])
        timestamps[:] = [t for t in timestamps if t > window_start]
        if len(timestamps) >= rpm_limit:
            return True
        timestamps.append(now)
        return False
