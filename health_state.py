"""Shared health state accessors and SQLite persistence (CQ-014 slice 9)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import deque

from config.db_config import HEALTH_STATE_DB as _DB_PATH
from config.sqlite_pool import pooled_sqlite_conn

from health_models import (
    BASE_COOLDOWN,
    LATENCY_WINDOW_SIZE,
    CooldownState,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_penalties,
    _quality_states,
    calc_cooldown,
)

logger = logging.getLogger(__name__)


def get_health(backend: str) -> str:
    with _lock:
        return _health_map.get(backend, "healthy")


def get_health_map() -> dict:
    with _lock:
        return dict(_health_map)


def is_cooled_down(backend: str) -> bool:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return False
        return time.monotonic() <= state.cooldown_until


def set_cooldown(backend: str, ttl: float = BASE_COOLDOWN) -> None:
    with _lock:
        state = _cooldown_states.setdefault(backend, CooldownState())
        state.cooldown_until = time.monotonic() + ttl


def get_cooldown_remaining(backend: str) -> float:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return 0.0
        return max(0, state.cooldown_until - time.monotonic())


def get_backend_state(backend: str) -> dict:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return {
                "state": "ok",
                "cooldown_until": 0.0,
                "last_error_class": None,
                "last_error_code": None,
            }
        return {
            "state": state.state,
            "cooldown_until": state.cooldown_until,
            "last_error_class": state.last_error_class,
            "last_error_code": state.last_error_code,
        }


def get_backend_quality(backend: str) -> dict:
    """Return quality counters for a backend (total_requests, empty_count, error_msg_count)."""
    with _lock:
        quality = _quality_states.get(backend)
        if not quality:
            return {"total_requests": 0, "empty_count": 0, "error_msg_count": 0}
        return {
            "total_requests": quality.total_requests,
            "empty_count": quality.empty_count,
            "error_msg_count": quality.error_msg_count,
        }


def get_latency_map() -> dict:
    with _lock:
        result = {}
        for name, quality in _quality_states.items():
            if quality.latencies:
                result[name] = sum(quality.latencies) / len(quality.latencies)
            else:
                result[name] = 1000.0
        return result


def clear_cooldown(backend: str) -> None:
    with _lock:
        state = _cooldown_states.get(backend)
        if not state:
            return
        state.cooldown_until = 0.0
        state.consecutive_failures = 0
        state.state = "ok"


def reset_all_state() -> None:
    with _lock:
        _health_map.clear()
        _cooldown_states.clear()
        _quality_states.clear()
        _quality_penalties.clear()


# ─── SQLite Persistence ───────────────────────────────────────────────────────


def _ensure_db_dir() -> None:
    os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS health_states (
            backend TEXT PRIMARY KEY,
            status TEXT,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cooldown_states (
            backend TEXT PRIMARY KEY,
            consecutive_failures INTEGER,
            current_cooldown REAL,
            cooldown_until REAL,
            last_error_code INTEGER,
            state TEXT,
            last_error_class TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_states (
            backend TEXT PRIMARY KEY,
            latencies TEXT,
            empty_count INTEGER,
            error_msg_count INTEGER,
            total_requests INTEGER,
            last_success REAL,
            last_failure REAL
        )
    """)


def save_health_state() -> None:
    """Persist health state to SQLite using the thread-local pool."""
    _ensure_db_dir()
    try:
        with pooled_sqlite_conn(_DB_PATH) as conn:
            _ensure_tables(conn)
            with _lock:
                _persist_health_map(conn)
                _persist_cooldown_states(conn)
                _persist_quality_states(conn)
    except Exception as exc:
        logger.warning("Failed to save health state: %s", exc)


def _persist_health_map(conn: sqlite3.Connection) -> None:
    for backend, status in _health_map.items():
        conn.execute(
            "INSERT OR REPLACE INTO health_states (backend, status, updated_at) VALUES (?, ?, ?)",
            (backend, status, time.time()),
        )


def _persist_cooldown_states(conn: sqlite3.Connection) -> None:
    for backend, state in _cooldown_states.items():
        conn.execute(
            "INSERT OR REPLACE INTO cooldown_states VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                backend,
                state.consecutive_failures,
                state.current_cooldown,
                state.cooldown_until,
                state.last_error_code,
                state.state,
                state.last_error_class,
            ),
        )


def _persist_quality_states(conn: sqlite3.Connection) -> None:
    for backend, quality in _quality_states.items():
        conn.execute(
            "INSERT OR REPLACE INTO quality_states VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                backend,
                json.dumps(list(quality.latencies)),
                quality.empty_count,
                quality.error_msg_count,
                quality.total_requests,
                quality.last_success,
                quality.last_failure,
            ),
        )


def load_health_state() -> int:
    """Load health state from SQLite. Returns count of loaded entries."""
    if not os.path.exists(_DB_PATH):
        return 0
    _ensure_db_dir()
    try:
        with pooled_sqlite_conn(_DB_PATH) as conn:
            _ensure_tables(conn)
            count = 0
            with _lock:
                for row in conn.execute("SELECT backend, status FROM health_states"):
                    _health_map[row[0]] = row[1]
                    count += 1

                for row in conn.execute("SELECT * FROM cooldown_states"):
                    # AUDIT-4-F6：cooldown_until 用 time.monotonic() 计算，重启归零。
                    # 直接加载上一进程的绝对值会导致 is_cooled_down 在"永不冷却"和
                    # "全熔断"间随机摇摆。重启时清零 cooldown_until，让 probe_loop 重新探测，
                    # 同时保留 consecutive_failures/error 统计（仅重置时间基准）。
                    _cooldown_states[row[0]] = CooldownState(
                        consecutive_failures=row[1],
                        current_cooldown=row[2],
                        cooldown_until=0.0,
                        last_error_code=row[4],
                        state=row[5],
                        last_error_class=row[6],
                    )

                for row in conn.execute("SELECT * FROM quality_states"):
                    _quality_states[row[0]] = QualityState(
                        latencies=deque(json.loads(row[1]), maxlen=LATENCY_WINDOW_SIZE),
                        empty_count=row[2],
                        error_msg_count=row[3],
                        total_requests=row[4],
                        last_success=row[5],
                        last_failure=row[6],
                    )
                    count += 1

            logger.info("Loaded health state: %d backends", count)
            return count
    except Exception as exc:
        logger.warning("Failed to load health state: %s", exc)
        return 0


def save_on_change() -> None:
    """Save state after each modification (called by health_recorder)."""
    try:
        save_health_state()
    except Exception as exc:
        logger.warning("health_state save failed: %s", exc, exc_info=True)
