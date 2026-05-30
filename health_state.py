"""Shared health state, cooldown math, and read-only accessors (CQ-014 slice 9)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

BASE_COOLDOWN = 5
MAX_COOLDOWN = 300
BACKOFF_FACTOR = 2
COOLDOWN_429_BASE = 30
COOLDOWN_AUTH_FIXED = 300

QUALITY_WINDOW = 50
LATENCY_WINDOW_SIZE = 20
LATENCY_PENALTY = 5000.0
FAILURE_THRESHOLD_MIN_REQUESTS = 5

_lock = threading.RLock()
_health_map: dict[str, str] = {}
_cooldown_states: dict[str, "CooldownState"] = {}
_quality_states: dict[str, "QualityState"] = {}
_quality_penalties: dict[str, float] = {}
QUALITY_PENALTY_DURATION = 1800


@dataclass
class CooldownState:
    consecutive_failures: int = 0
    current_cooldown: float = BASE_COOLDOWN
    cooldown_until: float = 0.0
    last_error_code: Optional[int] = None
    state: str = "ok"
    last_error_class: Optional[str] = None


@dataclass
class QualityState:
    response_lengths: deque = field(default_factory=lambda: deque(maxlen=QUALITY_WINDOW))
    latencies: deque = field(default_factory=lambda: deque(maxlen=LATENCY_WINDOW_SIZE))
    empty_count: int = 0
    error_msg_count: int = 0
    total_requests: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0


def calc_cooldown(failures: int, error_code: Optional[int] = None) -> float:
    if error_code in (401, 403):
        return COOLDOWN_AUTH_FIXED
    base = COOLDOWN_429_BASE if error_code == 429 else BASE_COOLDOWN
    cooldown = base * (BACKOFF_FACTOR ** (failures - 1))
    return min(cooldown, MAX_COOLDOWN)


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


# ─── SQLite Persistence ───────────────────────────────────────────────────

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

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
                    "INSERT OR REPLACE INTO quality_states VALUES (?, ?, ?, ?, ?, ?)",
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
            conn.close()
        except Exception as exc:
            logger.warning("Failed to save health state: %s", exc)


def load_health_state() -> int:
    """Load health state from SQLite. Returns count of loaded entries."""
    if not os.path.exists(_DB_PATH):
        return 0
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

        conn.close()
        logger.info("Loaded health state: %d backends", count)
        return count
    except Exception as exc:
        logger.warning("Failed to load health state: %s", exc)
        return 0


def save_on_change() -> None:
    """Save state after each modification (called by health_recorder)."""
    try:
        save_health_state()
    except Exception:
        pass
