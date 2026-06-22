"""SQLite persistence for health_state (CQ-014 slice 9)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import deque

from health_state import (
    LATENCY_WINDOW_SIZE,
    CooldownState,
    QualityState,
    _cooldown_states,
    _health_map,
    _lock,
    _quality_states,
)

logger = logging.getLogger(__name__)
_log = logger

_DB_PATH = os.environ.get("LIMA_HEALTH_STATE_DB", "data/health_state.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
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
    """Persist health state to SQLite."""
    with _lock:
        conn = None
        try:
            conn = _get_conn()
            _ensure_tables(conn)

            # Health map
            for backend, status in _health_map.items():
                conn.execute(
                    "INSERT OR REPLACE INTO health_states (backend, status, updated_at) VALUES (?, ?, ?)",
                    (backend, status, time.time()),
                )

            # Cooldown states
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

            # Quality states
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

            conn.commit()
        except Exception as exc:
            logger.warning("Failed to save health state: %s", exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def load_health_state() -> int:
    """Load health state from SQLite. Returns count of loaded entries."""
    if not os.path.exists(_DB_PATH):
        return 0
    conn = None
    try:
        conn = _get_conn()
        _ensure_tables(conn)
        count = 0

        with _lock:
            # Health map
            for row in conn.execute("SELECT backend, status FROM health_states"):
                _health_map[row[0]] = row[1]
                count += 1

            # Cooldown states
            for row in conn.execute("SELECT * FROM cooldown_states"):
                _cooldown_states[row[0]] = CooldownState(
                    consecutive_failures=row[1],
                    current_cooldown=row[2],
                    cooldown_until=row[3],
                    last_error_code=row[4],
                    state=row[5],
                    last_error_class=row[6],
                )

            # Quality states
            for row in conn.execute("SELECT * FROM quality_states"):
                _quality_states[row[0]] = QualityState(
                    latencies=deque(json.loads(row[1]), maxlen=LATENCY_WINDOW_SIZE),
                    empty_count=row[2],
                    error_msg_count=row[3],
                    total_requests=row[4],
                    last_success=row[5],
                    last_failure=row[6],
                )

        logger.info("Loaded health state: %d backends", count)
        return count
    except Exception as exc:
        logger.warning("Failed to load health state: %s", exc)
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def save_on_change() -> None:
    """Save state after each modification (called by health_recorder)."""
    try:
        save_health_state()
    except Exception as exc:
        _log.warning("health_state.py save failed: %s", type(exc).__name__)
