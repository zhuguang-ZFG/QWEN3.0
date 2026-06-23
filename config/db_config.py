"""Centralized database and storage configuration.

All database paths, Redis URLs, and storage-related environment variables
are read once at module load time. Consumers import from here instead of
calling os.environ.get() directly, ensuring consistent defaults and a
single place to audit configuration.

Add new variables here as production code migrates away from ad-hoc os.environ calls.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Base paths ─────────────────────────────────────────────────────────────────
LIMA_DATA_DIR: str = os.environ.get("LIMA_DATA_DIR", ".lima-data")
LIMA_DB_PATH: str = os.environ.get("LIMA_DB_PATH", "data/lima.db")


def get_lima_db_path() -> str:
    """Return the current LIMA_DB_PATH, reading the environment at call time.

    This allows tests to monkeypatch ``os.environ`` or ``config.db_config.LIMA_DB_PATH``
    after module import without leaking state across test cases.
    """
    return os.environ.get("LIMA_DB_PATH", LIMA_DB_PATH)


def get_lima_data_dir() -> str:
    """Return the current LIMA_DATA_DIR, reading the environment at call time."""
    return os.environ.get("LIMA_DATA_DIR", LIMA_DATA_DIR)


def get_session_db_path() -> str:
    """Return the current LIMA_SESSION_DB, reading the environment at call time."""
    return os.environ.get("LIMA_SESSION_DB", SESSION_DB)


# ── SQLite database paths ──────────────────────────────────────────────────────
BACKEND_PROFILE_DB: str = os.environ.get("LIMA_BACKEND_PROFILE_DB", "") or str(Path(LIMA_DATA_DIR) / "profiles.db")
BACKEND_RETIREMENT_DB: str = os.environ.get("LIMA_BACKEND_RETIREMENT_DB", "") or str(Path(LIMA_DATA_DIR) / "retirement.db")
HEALTH_STATE_DB: str = os.environ.get("LIMA_HEALTH_STATE_DB", "") or "data/health_state.db"
SESSION_DB: str = os.environ.get("LIMA_SESSION_DB", "") or str(Path(LIMA_DATA_DIR) / "session.db")
TOKEN_HEALTH_DB: str = os.environ.get("LIMA_TOKEN_HEALTH_DB", "") or str(Path(LIMA_DATA_DIR) / "token_health.db")
REQUEST_LOG_DB: str = os.environ.get("LIMA_REQUEST_LOG_DB", "") or str(Path(LIMA_DATA_DIR) / "request_log.db")
TOOL_AUDIT_DB: str = os.environ.get("LIMA_AUDIT_DB", "") or str(Path(LIMA_DATA_DIR) / "tool_audit.db")
WORKER_DB: str = os.environ.get("LIMA_WORKER_DB", "") or str(Path(LIMA_DATA_DIR) / "worker_registry.db")
WEIGHTS_PATH: str = os.environ.get("LIMA_WEIGHTS_PATH", "") or str(Path(LIMA_DATA_DIR) / "routing_weights.json")

# ── User identity ──────────────────────────────────────────────────────────────
PROFILES_DIR: str = os.environ.get("LIMA_PROFILES_DIR", "/tmp/lima_profiles")
LESSONS_DIR: str = os.environ.get("LIMA_LESSONS_DIR", "/tmp/lima_lessons")

# ── Redis ──────────────────────────────────────────────────────────────────────
DEVICE_REDIS_URL: str = os.environ.get("LIMA_DEVICE_REDIS_URL", "")
