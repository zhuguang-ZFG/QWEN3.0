"""SQLite persistence for health state with event-loop-safe debounced writes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque

from config.db_config import HEALTH_STATE_DB as _DB_PATH
from config.sqlite_pool import pooled_sqlite_conn
from health_models import (
    LATENCY_WINDOW_SIZE,
    CooldownState,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_states,
)

logger = logging.getLogger(__name__)

_SAVE_DEBOUNCE_SEC = 5.0
_save_timer: threading.Timer | None = None
_save_timer_lock = threading.Lock()


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


def _schedule_save() -> None:
    """Schedule a debounced SQLite persist in a background thread.

    AUDIT-5-O1 follow-up: the old synchronous ``save_on_change()`` blocked the
    async event loop on every backend health change. Batching writes in a
    background thread eliminates that stall while still persisting state.
    """
    global _save_timer
    with _save_timer_lock:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = threading.Timer(_SAVE_DEBOUNCE_SEC, _run_pending_save)
        _save_timer.daemon = True
        _save_timer.start()


def _run_pending_save() -> None:
    """Flush health state to SQLite and clear the timer reference."""
    global _save_timer
    with _save_timer_lock:
        _save_timer = None
    try:
        save_health_state()
    except Exception as exc:
        logger.warning("debounced health state save failed: %s", exc)


def flush_pending_save() -> None:
    """Cancel any pending debounced save and persist immediately."""
    global _save_timer
    timer: threading.Timer | None = None
    with _save_timer_lock:
        timer = _save_timer
        _save_timer = None
    if timer is not None:
        timer.cancel()
    save_health_state()


def save_on_change() -> None:
    """Persist state after each modification without blocking the event loop.

    Called synchronously from ``health_recorder`` on every backend success or
    failure. When invoked from the async event loop (e.g. ``http_async``), the
    SQLite write is debounced to a background thread so a storm of backend
    health updates does not stall ``/health/ready`` and other async handlers.
    When called from a synchronous context or a worker thread, the write is
    performed directly (no event loop to block).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Not running on the event loop; synchronous persist is safe here.
        try:
            save_health_state()
        except Exception as exc:
            logger.warning("health_state save failed: %s", exc, exc_info=True)
        return
    _schedule_save()
