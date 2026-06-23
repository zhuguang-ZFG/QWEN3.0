"""Centralized application settings (P1-2 phase 1).

Non-backend configuration values grouped by domain. Backend API keys remain in
backends_registry because they are provider-specific credentials, not shared
application settings.

Database/Redis/storage paths live in config.db_config; this module re-exports
them for convenience and adds flags/security/paths that are not DB-related.

All values are read once at module import time. Run-time mutation is not
supported; tests should patch the module-level singletons.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import db_config


@dataclass
class DatabaseConfig:
    data_dir: str = db_config.LIMA_DATA_DIR
    db_path: str = db_config.LIMA_DB_PATH
    session_db: str = db_config.SESSION_DB
    backend_profile_db: str = db_config.BACKEND_PROFILE_DB
    backend_retirement_db: str = db_config.BACKEND_RETIREMENT_DB
    health_state_db: str = db_config.HEALTH_STATE_DB
    token_health_db: str = db_config.TOKEN_HEALTH_DB


@dataclass
class RedisConfig:
    device_redis_url: str = db_config.DEVICE_REDIS_URL


@dataclass
class SecurityConfig:
    admin_token: str = os.environ.get("LIMA_ADMIN_TOKEN", "")
    admin_login_per_min: int = int(os.environ.get("LIMA_ADMIN_LOGIN_PER_MIN", "10"))
    rate_limit_disable: bool = os.environ.get("LIMA_RATE_LIMIT_DISABLE", "").strip().lower() in {"1", "true", "yes", "on"}
    api_key: str = os.environ.get("LIMA_API_KEY", "")
    api_keys: str = os.environ.get("LIMA_API_KEYS", "")
    allow_anonymous: bool = os.environ.get("LIMA_ALLOW_ANONYMOUS", "").strip().lower() in {"1", "true", "yes", "on"}


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
