"""Centralized application settings (P1-2 phase 1).

Non-backend configuration values grouped by domain. Backend API keys remain in
backends_registry because they are provider-specific credentials, not shared
application settings.

All values are read once at module import time. Run-time mutation is not
supported; tests should patch os.environ and reload the module if needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    data_dir: str = os.environ.get("LIMA_DATA_DIR", ".lima-data")
    db_path: str = os.environ.get("LIMA_DB_PATH", "data/lima.db")
    session_db: str = os.environ.get("LIMA_SESSION_DB", "")
    backend_profile_db: str = os.environ.get("LIMA_BACKEND_PROFILE_DB", "")
    backend_retirement_db: str = os.environ.get("LIMA_BACKEND_RETIREMENT_DB", "")
    health_state_db: str = os.environ.get("LIMA_HEALTH_STATE_DB", "")
    token_health_db: str = os.environ.get("LIMA_TOKEN_HEALTH_DB", "")


@dataclass
class RedisConfig:
    device_redis_url: str = os.environ.get("LIMA_DEVICE_REDIS_URL", "")


@dataclass
class SecurityConfig:
    admin_token: str = os.environ.get("LIMA_ADMIN_TOKEN", "")
    admin_login_per_min: int = int(os.environ.get("LIMA_ADMIN_LOGIN_PER_MIN", "10"))
    rate_limit_disable: bool = os.environ.get("LIMA_RATE_LIMIT_DISABLE", "").strip().lower() in {"1", "true", "yes", "on"}
    api_key: str = os.environ.get("LIMA_API_KEY", "")
    api_keys: str = os.environ.get("LIMA_API_KEYS", "")


@dataclass
class PathsConfig:
    profiles_dir: str = os.environ.get("LIMA_PROFILES_DIR", "/tmp/lima_profiles")
    lessons_dir: str = os.environ.get("LIMA_LESSONS_DIR", "/tmp/lima_lessons")


@dataclass
class FeatureFlags:
    debug: bool = os.environ.get("LIMA_DEBUG", "") == "1"
    memory_embed: bool = os.environ.get("LIMA_MEMORY_EMBED", "1").strip().lower() in {"1", "true", "yes"}
    verify_host: bool = os.environ.get("LIMA_VERIFY_HOST", "1").strip().lower() in {"1", "true", "yes"}


DB = DatabaseConfig()
REDIS = RedisConfig()
SECURITY = SecurityConfig()
PATHS = PathsConfig()
FLAGS = FeatureFlags()


def resolve_session_db() -> str:
    """Return the effective session DB path, falling back to data_dir."""
    return DB.session_db or str(Path(DB.data_dir) / "session.db")


def resolve_backend_profile_db() -> str:
    """Return the effective backend profile DB path."""
    return DB.backend_profile_db or str(Path(DB.data_dir) / "profiles.db")


def resolve_backend_retirement_db() -> str:
    """Return the effective backend retirement DB path."""
    return DB.backend_retirement_db or str(Path(DB.data_dir) / "retirement.db")


def resolve_token_health_db() -> str:
    """Return the effective token health DB path."""
    return DB.token_health_db or str(Path(DB.data_dir) / "token_health.db")
