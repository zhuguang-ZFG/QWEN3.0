"""Centralized application settings dataclasses (P1-2 phase 1).

Non-backend configuration values grouped by domain. Backend API keys remain in
backends_registry because they are provider-specific credentials, not shared
application settings.

Database/Redis/storage paths live in config.db_config; this module provides the
dataclass definitions and runtime helper functions used by config.settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
    request_log_db: str = db_config.REQUEST_LOG_DB
    tool_audit_db: str = db_config.TOOL_AUDIT_DB
    worker_db: str = db_config.WORKER_DB


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
    jwt_secret: str = os.environ.get("LIMA_JWT_SECRET", "").strip()
    device_auth_rate_redis: str = os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS", "auto").strip().lower()
    device_auth_rate_redis_url: str = os.environ.get("LIMA_DEVICE_AUTH_RATE_REDIS_URL", "").strip()


@dataclass
class PathsConfig:
    profiles_dir: str = os.environ.get("LIMA_PROFILES_DIR", "/tmp/lima_profiles")
    lessons_dir: str = os.environ.get("LIMA_LESSONS_DIR", "/tmp/lima_lessons")
    project_root: str = os.environ.get("LIMA_PROJECT_ROOT", "")
    code_dir: str = os.environ.get("LIMA_CODE_DIR", "/opt/lima-router")
    routing_model_path: str = os.environ.get("LIMA_ROUTING_MODEL_PATH", "data/routing_model.json")
    local_router_url: str = os.environ.get(
        "LOCAL_ROUTER_URL", "http://127.0.0.1:11434/v1/chat/completions"
    )


@dataclass
class FeatureFlags:
    debug: bool = os.environ.get("LIMA_DEBUG", "") == "1"
    memory_embed: bool = os.environ.get("LIMA_MEMORY_EMBED", "1").strip().lower() in {"1", "true", "yes"}
    verify_host: bool = os.environ.get("LIMA_VERIFY_HOST", "1").strip().lower() in {"1", "true", "yes"}
    device_llm_planner: bool = os.environ.get("LIMA_DEVICE_LLM_PLANNER", "0") == "1"
    allow_http_backends: bool = (
        os.environ.get("LIMA_ALLOW_HTTP_BACKENDS", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    distill_log: bool = os.environ.get("DISTILL_LOG", "0") == "1"
    wechat_dev_login: bool = (
        os.environ.get("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    xiaozhi_dev_static_login_code: bool = (
        os.environ.get("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    public_demo: bool = (
        os.environ.get("LIMA_PUBLIC_DEMO_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    public_demo_max_per_minute: int = max(
        1,
        min(60, int(os.environ.get("LIMA_PUBLIC_DEMO_MAX_PER_MINUTE", "6") or "6")),
    )
    health_show_errors: bool = (
        os.environ.get("LIMA_HEALTH_SHOW_ERRORS", "0").strip().lower() in {"1", "true", "yes"}
    )
    enable_leann: bool = os.environ.get("LIMA_ENABLE_LEANN", "") == "1"
    runtime_env: str = os.environ.get("LIMA_RUNTIME_ENV", "").strip().lower()
    enable_local_proxies: bool = (
        os.environ.get("LIMA_ENABLE_LOCAL_PROXIES", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    runtime_local_proxies: bool = (
        os.environ.get("LIMA_RUNTIME_LOCAL_PROXIES", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    healthcheck_enabled: bool = (
        os.environ.get("LIMA_HEALTHCHECK_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    )
    device_mode: bool = os.environ.get("LIMA_DEVICE_MODE", "").strip() == "1"


@dataclass
class EvalConfig:
    via_router_enabled: bool = os.environ.get("LIMA_EVAL_TOPOLOGY", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    via_router_url: str = os.environ.get("LIMA_EVAL_VIA_ROUTER_URL", "").strip()
    windows_router_url: str = os.environ.get("LIMA_EVAL_WINDOWS_ROUTER", "").strip()


@dataclass
class BackendOpsConfig:
    probe_interval: int = int(os.environ.get("LIMA_PROBE_INTERVAL", "300"))
    operator_probe_timeout: float = float(os.environ.get("LIMA_OPERATOR_PROBE_TIMEOUT", "25"))
    operator_probe_workers: int = int(os.environ.get("LIMA_OPERATOR_PROBE_WORKERS", "4"))
    retirement_reload_sec: float = float(os.environ.get("LIMA_BACKEND_RETIREMENT_RELOAD_SEC", "300"))
    dynamic_admission: bool = os.environ.get("LIMA_DYNAMIC_ADMISSION", "0") == "1"


@dataclass
class BrandConfig:
    public_model_name: str = os.environ.get("PUBLIC_MODEL_NAME", "LiMa")
    public_model_name_cn: str = os.environ.get("PUBLIC_MODEL_NAME_CN", "力码")
    company_name_cn: str = os.environ.get("COMPANY_NAME_CN", "深圳市动力巢科技有限公司")
    company_name_en: str = os.environ.get("COMPANY_NAME_EN", "DongLiCao Technology (Shenzhen)")
    company_short_cn: str = os.environ.get("COMPANY_SHORT_CN", "动力巢科技")
    user_agent: str = os.environ.get("LIMA_USER_AGENT", "LiMa/2.0")


@dataclass
class EmbeddingConfig:
    url: str = os.environ.get("LIMA_EMBEDDINGS_URL", "https://api.jina.ai/v1/embeddings")
    jina_api_key: str = os.environ.get("JINA_API_KEY", "")
    gfw_proxy: str = os.environ.get("GFW_PROXY", "")
    google_inventory_proxy: str = os.environ.get("GOOGLE_INVENTORY_PROXY", "").strip()
    mcp_inventory_proxy: str = os.environ.get("MCP_INVENTORY_PROXY", "").strip()


@dataclass
class DeviceConfig:
    tokens: str = os.environ.get("LIMA_DEVICE_TOKENS", "")
    digital_human_default_device_id: str = (
        os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "web-tester").strip()
    )
    digital_human_default_token: str = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN", "").strip()
    mqtt_enabled: bool = (
        os.environ.get("LIMA_DEVICE_MQTT_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
    )
    mqtt_broker: str = os.environ.get("LIMA_DEVICE_MQTT_BROKER", "localhost")
    mqtt_port: int = int(os.environ.get("LIMA_DEVICE_MQTT_PORT", "1883"))
    mqtt_client_id: str = os.environ.get("LIMA_DEVICE_MQTT_CLIENT_ID", "lima-router")
    session_bus: str = os.environ.get("LIMA_DEVICE_SESSION_BUS", "").strip().lower()
    redis_task_ttl: int = int(os.environ.get("LIMA_REDIS_TASK_TTL", "2592000"))
    auth_register_per_min: int = int(os.environ.get("LIMA_DEVICE_AUTH_REGISTER_PER_MIN", "5") or "5")
    auth_login_per_min: int = int(os.environ.get("LIMA_DEVICE_AUTH_LOGIN_PER_MIN", "20") or "20")
    auth_sms_per_min: int = int(os.environ.get("LIMA_DEVICE_AUTH_SMS_PER_MIN", "10") or "10")
    activation_code: str = os.environ.get("LIMA_XIAOZHI_ACTIVATION_CODE", "").strip()
    login_code: str = os.environ.get("LIMA_XIAOZHI_LOGIN_CODE", "").strip()
    captcha_required: bool = (
        os.environ.get("LIMA_XIAOZHI_CAPTCHA_REQUIRED", "").strip().lower() in {"1", "true", "yes"}
    )
    redis_memory_index_ttl: int = int(os.environ.get("LIMA_REDIS_MEMORY_INDEX_TTL", "2592000"))
    redis_ledger_ttl: int = int(os.environ.get("LIMA_REDIS_LEDGER_TTL", "7776000"))


@dataclass
class SessionMemoryConfig:
    enabled: bool = os.environ.get("LIMA_SESSION_MEMORY", "0") == "1"
    admin: bool = os.environ.get("LIMA_MEMORY_ADMIN", "0") == "1"
    inbox: str = os.environ.get(
        "LIMA_MEMORY_INBOX",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory_inbox"),
    )
    consolidation_interval: int = int(os.environ.get("LIMA_MEMORY_CONSOLIDATION_INTERVAL", "300"))
    outcome_ledger_enabled: bool = (
        os.environ.get("LIMA_OUTCOME_LEDGER", "1").strip().lower() in {"1", "true", "yes"}
    )
    outcome_db: str = os.environ.get(
        "LIMA_OUTCOME_DB",
        str(Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "outcome_ledger.db"),
    )


@dataclass
class DigitalHumanConfig:
    directory: str = os.environ.get("LIMA_DIGITAL_HUMAN_DIR", "").strip()
    device_id: str = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "web-tester").strip()
    device_name: str = (
        os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_NAME", "LiMa 星云数字人").strip()
    )
    client_id: str = os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_CLIENT_ID", "web_test_client").strip()
    wakeword_enabled: bool = (
        os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_WAKEUP_WORD_ENABLED", "false").strip().lower()
        == "true"
    )


@dataclass
class GeminiConfig:
    live_model: str = os.environ.get("LIMA_GEMINI_LIVE_MODEL", "models/gemini-3.1-flash-live-preview")


@dataclass
class OutcomeConfig:
    ingest_per_min: int = int(os.environ.get("LIMA_OUTCOME_INGEST_PER_MIN", "60"))


@dataclass
class OtaConfig:
    state_path: str | None = os.environ.get("LIMA_DEVICE_OTA_STATE_PATH") or None
    signing_public_key: str = os.environ.get("LIMA_OTA_SIGNING_PUBLIC_KEY", "")


@dataclass
class UploadConfig:
    per_min: int = int(os.environ.get("LIMA_UPLOAD_PER_MIN", "30"))
    token_secret: str = os.environ.get("LIMA_UPLOAD_TOKEN_SECRET") or os.environ.get("LIMA_JWT_SECRET", "")
    public_get_enabled: bool = (
        os.environ.get("LIMA_UPLOAD_PUBLIC_GET", "0").strip().lower() in {"1", "true", "yes"}
    )
    token_ttl: int = int(os.environ.get("LIMA_UPLOAD_TOKEN_TTL", "86400"))


@dataclass
class ObservabilityConfig:
    telemetry_jsonl_max_bytes: int = int(
        os.environ.get("LIMA_TELEMETRY_JSONL_MAX_BYTES", str(1024 * 1024))
    )
    openobserve_enabled: bool = (
        os.environ.get("OPENOBSERVE_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    )
    prometheus_metrics: bool = (
        os.environ.get("LIMA_PROMETHEUS_METRICS", "0").strip().lower() in {"1", "true", "yes", "on"}
    )
    structured_logging: bool = (
        os.environ.get("LIMA_STRUCTURED_LOGGING", "0").strip().lower() in {"1", "true", "yes"}
    )
    service_name: str = os.environ.get("LIMA_SERVICE_NAME", "lima-router")
    routing_guard_enabled: bool = (
        os.environ.get("LIMA_ROUTING_GUARD_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
    )
    routing_guard_window_sec: int = int(os.environ.get("LIMA_ROUTING_GUARD_WINDOW_SEC", "600"))
    routing_guard_quarantine_sec: int = int(
        os.environ.get("LIMA_ROUTING_GUARD_QUARANTINE_SEC", "180")
    )
    routing_guard_failure_threshold: int = int(
        os.environ.get("LIMA_ROUTING_GUARD_FAILURE_THRESHOLD", "3")
    )


@dataclass
class MonitoringConfig:
    sentry_dsn: str = os.environ.get("SENTRY_DSN", "")


@dataclass
class IntegrationsConfig:
    supabase_url: str = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key: str = os.environ.get("SUPABASE_SECRET", "").strip()
    langsmith_key: str = os.environ.get("LANGSMITH_API_KEY", "").strip()
    gitee_token: str = (
        os.environ.get("GITEE_TOKEN", "").strip() or os.environ.get("GITEE_ACCESS_TOKEN", "").strip()
    )


@dataclass
class FleetConfig:
    allowed_commands: str = os.environ.get("LIMA_FLEET_ALLOWED_COMMANDS", "").strip()


def get_key_pool_raw(provider: str) -> str:
    """Return the raw key-pool value for *provider* from the environment."""
    import re

    safe = re.sub(r"[^A-Za-z0-9]+", "_", provider).strip("_").upper()
    return os.environ.get(f"LIMA_KEY_POOL_{safe}", "")


def resolve_backend_key(key: str) -> str:
    """Resolve a backend key, expanding ``$ENV_VAR`` references at call time."""
    if key.startswith("$"):
        return os.environ.get(key.lstrip("$"), "")
    return key


def get_env(name: str, default: str = "") -> str:
    """Read a dynamic environment variable at call time.

    Used for env names that are not known until runtime (e.g. per-backend key_env_var).
    """
    return os.environ.get(name, default)
