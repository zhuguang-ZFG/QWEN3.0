"""SQLite-backed daily/monthly quota + in-memory RPM tracker."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from client_keys.models import ClientKey
from client_keys.storage import _hash_token

_log = logging.getLogger(__name__)

_RPM_WINDOW_SECONDS = 60.0


@dataclass
class _RpmWindow:
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=10000))


class QuotaTracker:
    """Track daily/monthly quota and RPM limits for client API keys.

    Daily/monthly counters are persisted in SQLite so they are shared across
    workers. RPM is tracked per-process in memory; see PONYTAIL-DEBT.md for
    the multi-worker limitation.
    """

    def __init__(self, db_path: str, rpm_window_seconds: float = _RPM_WINDOW_SECONDS) -> None:
        self._db_path = db_path
        self._rpm_window_seconds = rpm_window_seconds
        self._lock = threading.Lock()
        self._rpm_windows: dict[str, _RpmWindow] = {}
        self._ensure_schema()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_key_usage (
                    token_hash TEXT PRIMARY KEY,
                    day TEXT NOT NULL,
                    month TEXT NOT NULL,
                    daily_count INTEGER NOT NULL DEFAULT 0,
                    monthly_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at REAL
                )
                """
            )
            conn.commit()

    def _current_counts(self, conn: sqlite3.Connection, token_hash: str, day: str, month: str) -> tuple[int, int]:
        row = conn.execute(
            "SELECT day, month, daily_count, monthly_count FROM client_key_usage WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return 0, 0
        daily = 0 if row["day"] != day else row["daily_count"]
        monthly = 0 if row["month"] != month else row["monthly_count"]
        return daily, monthly

    def _persist_consumption(
        self,
        conn: sqlite3.Connection,
        token_hash: str,
        day: str,
        month: str,
        daily_count: int,
        monthly_count: int,
        now: float,
    ) -> None:
        conn.execute(
            """
            INSERT INTO client_key_usage (token_hash, day, month, daily_count, monthly_count, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_hash) DO UPDATE SET
                day = excluded.day,
                month = excluded.month,
                daily_count = excluded.daily_count,
                monthly_count = excluded.monthly_count,
                last_used_at = excluded.last_used_at
            """,
            (token_hash, day, month, daily_count + 1, monthly_count + 1, now),
        )

    def try_consume_quota(self, key: ClientKey) -> tuple[bool, str]:
        """Atomically check and consume quota.

        Returns (allowed, reason). Reason is empty on success.
        """
        token_hash = _hash_token(key.key_value)
        now = time.time()
        day = _now_day()
        month = _now_month()

        if key.rate_limit_rpm > 0 and self._rpm_exceeded(token_hash, key.rate_limit_rpm, now):
            return False, "rpm_limit"

        try:
            with self._lock, self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                daily_count, monthly_count = self._current_counts(conn, token_hash, day, month)
                if key.quota_daily > 0 and daily_count >= key.quota_daily:
                    conn.rollback()
                    return False, "daily_limit"
                if key.quota_monthly > 0 and monthly_count >= key.quota_monthly:
                    conn.rollback()
                    return False, "monthly_limit"
                self._persist_consumption(conn, token_hash, day, month, daily_count, monthly_count, now)
                conn.commit()
        except sqlite3.Error as exc:
            _log.warning("client_keys: quota consumption failed: %s", exc)
            return False, "quota_error"
        return True, ""

    def check_key_quota(self, key: ClientKey) -> bool:
        if not key.enabled:
            return False
        token_hash = _hash_token(key.key_value)
        day = _now_day()
        month = _now_month()
        try:
            with self._lock, self._connection() as conn:
                row = conn.execute(
                    "SELECT day, month, daily_count, monthly_count FROM client_key_usage WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
        except sqlite3.Error as exc:
            _log.warning("client_keys: quota check failed: %s", exc)
            return False
        if row is None:
            return True
        daily_count = 0 if row["day"] != day else row["daily_count"]
        monthly_count = 0 if row["month"] != month else row["monthly_count"]
        if key.quota_daily > 0 and daily_count >= key.quota_daily:
            return False
        if key.quota_monthly > 0 and monthly_count >= key.quota_monthly:
            return False
        return True

    def usage_summary(self, key_value: str) -> dict:
        token_hash = _hash_token(key_value)
        day = _now_day()
        month = _now_month()
        try:
            with self._lock, self._connection() as conn:
                row = conn.execute(
                    "SELECT day, month, daily_count, monthly_count, last_used_at FROM client_key_usage WHERE token_hash = ?",
                    (token_hash,),
                ).fetchone()
        except sqlite3.Error as exc:
            _log.warning("client_keys: usage summary failed: %s", exc)
            return {"daily_count": 0, "monthly_count": 0, "last_used_at": None}
        if row is None:
            return {"daily_count": 0, "monthly_count": 0, "last_used_at": None}
        return {
            "daily_count": 0 if row["day"] != day else row["daily_count"],
            "monthly_count": 0 if row["month"] != month else row["monthly_count"],
            "last_used_at": row["last_used_at"],
        }

    def clear_token(self, key_value: str) -> None:
        token_hash = _hash_token(key_value)
        self._rpm_windows.pop(token_hash, None)
        try:
            with self._lock, self._connection() as conn:
                conn.execute("DELETE FROM client_key_usage WHERE token_hash = ?", (token_hash,))
                conn.commit()
        except sqlite3.Error as exc:
            _log.warning("client_keys: failed to clear usage for token: %s", exc)

    def _rpm_exceeded(self, token_hash: str, rpm_limit: int, now: float) -> bool:
        window = self._rpm_windows.setdefault(token_hash, _RpmWindow())
        cutoff = now - self._rpm_window_seconds
        while window.timestamps and window.timestamps[0] <= cutoff:
            window.timestamps.popleft()
        if len(window.timestamps) >= rpm_limit:
            return True
        window.timestamps.append(now)
        return False


def _now_day() -> str:
    return time.strftime("%Y-%m-%d")


def _now_month() -> str:
    return time.strftime("%Y-%m")
