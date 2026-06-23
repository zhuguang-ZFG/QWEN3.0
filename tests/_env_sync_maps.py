"""Domain-specific env-to-singleton mappings for the test monkeypatch wrapper."""

from __future__ import annotations

import os
from typing import Any, Callable


def _bool_env(value: str | None, truthy: frozenset[str] | None = None) -> bool:
    if truthy is None:
        truthy = frozenset({"1", "true", "yes", "on"})
    return (value or "").strip().lower() in truthy


def _strip_or_empty(value: str | None) -> str:
    return (value or "").strip()


def _parse_float(value: str | None, default: str) -> float:
    try:
        return float(value or default)
    except (ValueError, TypeError):
        return float(default)


def _clamp_public_demo_rate(value: str | None) -> int:
    try:
        return max(1, min(60, int(value or "6")))
    except ValueError:
        return 6


def _security_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_ADMIN_TOKEN": (settings.SECURITY, "admin_token", lambda v: v or ""),
        "LIMA_API_KEY": (settings.SECURITY, "api_key", lambda v: v or ""),
        "LIMA_JWT_SECRET": (settings.SECURITY, "jwt_secret", lambda v: (v or "").strip()),
    }


def _device_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_DEVICE_TOKENS": (settings.DEVICE, "tokens", lambda v: v or ""),
        "LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID": (
            settings.DEVICE,
            "digital_human_default_device_id",
            lambda v: (v or "web-tester").strip(),
        ),
        "LIMA_DIGITAL_HUMAN_DEFAULT_TOKEN": (
            settings.DEVICE,
            "digital_human_default_token",
            lambda v: (v or "").strip(),
        ),
        "LIMA_DEVICE_MQTT_ENABLED": (
            settings.DEVICE,
            "mqtt_enabled",
            lambda v: _bool_env(v, frozenset({"1", "true", "yes"})),
        ),
        "LIMA_DEVICE_MQTT_BROKER": (settings.DEVICE, "mqtt_broker", lambda v: v or "localhost"),
        "LIMA_DEVICE_MQTT_PORT": (settings.DEVICE, "mqtt_port", lambda v: int(v or "1883")),
        "LIMA_DEVICE_MQTT_CLIENT_ID": (settings.DEVICE, "mqtt_client_id", lambda v: v or "lima-router"),
        "LIMA_DEVICE_SESSION_BUS": (settings.DEVICE, "session_bus", lambda v: (v or "").strip().lower()),
        "LIMA_REDIS_TASK_TTL": (settings.DEVICE, "redis_task_ttl", lambda v: int(v or "2592000")),
        "LIMA_REDIS_MEMORY_INDEX_TTL": (settings.DEVICE, "redis_memory_index_ttl", lambda v: int(v or "2592000")),
        "LIMA_REDIS_LEDGER_TTL": (settings.DEVICE, "redis_ledger_ttl", lambda v: int(v or "7776000")),
        "LIMA_DEVICE_AUTH_REGISTER_PER_MIN": (settings.DEVICE, "auth_register_per_min", lambda v: int(v or "5")),
        "LIMA_DEVICE_AUTH_LOGIN_PER_MIN": (settings.DEVICE, "auth_login_per_min", lambda v: int(v or "20")),
        "LIMA_DEVICE_AUTH_SMS_PER_MIN": (settings.DEVICE, "auth_sms_per_min", lambda v: int(v or "10")),
        "LIMA_XIAOZHI_ACTIVATION_CODE": (settings.DEVICE, "activation_code", _strip_or_empty),
        "LIMA_XIAOZHI_LOGIN_CODE": (settings.DEVICE, "login_code", _strip_or_empty),
        "LIMA_XIAOZHI_CAPTCHA_REQUIRED": (settings.DEVICE, "captcha_required", _bool_env),
    }


def _session_memory_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_SESSION_MEMORY": (settings.SESSION_MEMORY, "enabled", lambda v: v == "1"),
        "LIMA_MEMORY_ADMIN": (settings.SESSION_MEMORY, "admin", lambda v: v == "1"),
        "LIMA_MEMORY_INBOX": (settings.SESSION_MEMORY, "inbox", lambda v: v or ""),
        "LIMA_MEMORY_CONSOLIDATION_INTERVAL": (
            settings.SESSION_MEMORY,
            "consolidation_interval",
            lambda v: int(v or "300"),
        ),
        "LIMA_OUTCOME_LEDGER": (
            settings.SESSION_MEMORY,
            "outcome_ledger_enabled",
            lambda v: _bool_env(v, frozenset({"1", "true", "yes"})),
        ),
        "LIMA_OUTCOME_DB": (settings.SESSION_MEMORY, "outcome_db", lambda v: v or ""),
    }


def _brand_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "PUBLIC_MODEL_NAME": (settings.BRAND, "public_model_name", lambda v: v or "LiMa"),
        "PUBLIC_MODEL_NAME_CN": (settings.BRAND, "public_model_name_cn", lambda v: v or "力码"),
        "COMPANY_NAME_CN": (
            settings.BRAND,
            "company_name_cn",
            lambda v: v or "深圳市动力巢科技有限公司",
        ),
        "COMPANY_NAME_EN": (
            settings.BRAND,
            "company_name_en",
            lambda v: v or "DongLiCao Technology (Shenzhen)",
        ),
        "COMPANY_SHORT_CN": (settings.BRAND, "company_short_cn", lambda v: v or "动力巢科技"),
        "LIMA_USER_AGENT": (settings.BRAND, "user_agent", lambda v: v or "LiMa/2.0"),
    }


def _flags_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "DISTILL_LOG": (settings.FLAGS, "distill_log", lambda v: v == "1"),
        "LIMA_XIAOZHI_WECHAT_DEV_LOGIN": (settings.FLAGS, "wechat_dev_login", _bool_env),
        "LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE": (
            settings.FLAGS,
            "xiaozhi_dev_static_login_code",
            _bool_env,
        ),
        "LIMA_PUBLIC_DEMO_ENABLED": (settings.FLAGS, "public_demo", _bool_env),
        "LIMA_PUBLIC_DEMO_MAX_PER_MINUTE": (
            settings.FLAGS,
            "public_demo_max_per_minute",
            _clamp_public_demo_rate,
        ),
        "LIMA_XIAOZHI_COMPAT_ENABLED": (
            settings.FLAGS,
            "xiaozhi_compat",
            lambda v: _bool_env(v, frozenset({"1", "true", "yes"})),
        ),
        "LIMA_HEALTH_SHOW_ERRORS": (
            settings.FLAGS,
            "health_show_errors",
            lambda v: _bool_env(v, frozenset({"1", "true", "yes"})),
        ),
        "LIMA_ENABLE_LEANN": (settings.FLAGS, "enable_leann", lambda v: v == "1"),
        "LIMA_RUNTIME_ENV": (settings.FLAGS, "runtime_env", lambda v: (v or "").strip().lower()),
        "LIMA_ENABLE_LOCAL_PROXIES": (settings.FLAGS, "enable_local_proxies", _bool_env),
        "LIMA_RUNTIME_LOCAL_PROXIES": (settings.FLAGS, "runtime_local_proxies", _bool_env),
        "LIMA_HEALTHCHECK_ENABLED": (settings.FLAGS, "healthcheck_enabled", _bool_env),
        "LIMA_DEVICE_MODE": (settings.FLAGS, "device_mode", lambda v: (v or "").strip() == "1"),
    }


def _digital_human_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_DIGITAL_HUMAN_DIR": (
            settings.DIGITAL_HUMAN,
            "directory",
            lambda v: (v or "").strip(),
        ),
        "LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID": (
            settings.DIGITAL_HUMAN,
            "device_id",
            lambda v: (v or "web-tester").strip(),
        ),
        "LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_NAME": (
            settings.DIGITAL_HUMAN,
            "device_name",
            lambda v: (v or "LiMa 星云数字人").strip(),
        ),
        "LIMA_DIGITAL_HUMAN_DEFAULT_CLIENT_ID": (
            settings.DIGITAL_HUMAN,
            "client_id",
            lambda v: (v or "web_test_client").strip(),
        ),
        "LIMA_DIGITAL_HUMAN_DEFAULT_WAKEUP_WORD_ENABLED": (
            settings.DIGITAL_HUMAN,
            "wakeword_enabled",
            lambda v: (v or "").strip().lower() == "true",
        ),
    }


def _voice_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_VOICE_ENABLED": (
            settings.VOICE,
            "enabled",
            lambda v: (v or "").strip().lower() in {"1", "true", "yes"},
        ),
        "LIMA_VOICE_ASR_PROVIDER": (
            settings.VOICE,
            "asr_provider",
            lambda v: (v or "funasr").strip().lower(),
        ),
        "LIMA_VOICE_TTS_PROVIDER": (
            settings.VOICE,
            "tts_provider",
            lambda v: (v or "edge").strip().lower(),
        ),
        "LIMA_VOICE_VAD_PROVIDER": (
            settings.VOICE,
            "vad_provider",
            lambda v: (v or "silero").strip().lower(),
        ),
        "LIMA_VOICE_MODEL_DIR": (
            settings.VOICE,
            "model_dir",
            lambda v: v or "data/voice_models",
        ),
        "LIMA_VOICE_MAX_AUDIO_BYTES": (
            settings.VOICE,
            "max_audio_bytes",
            lambda v: int(v or "1048576"),
        ),
    }


def _voiceprint_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_VOICEPRINT_MODE": (
            settings.VOICEPRINT,
            "mode",
            lambda v: (v or "local").strip().lower(),
        ),
        "LIMA_VOICEPRINT_API_URL": (settings.VOICEPRINT, "api_url", _strip_or_empty),
        "LIMA_VOICEPRINT_API_KEY": (settings.VOICEPRINT, "api_key", _strip_or_empty),
        "LIMA_VOICEPRINT_SIMILARITY_THRESHOLD": (
            settings.VOICEPRINT,
            "similarity_threshold",
            lambda v: _parse_float(v, "0.6"),
        ),
    }


def _gemini_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_GEMINI_LIVE_MODEL": (
            settings.GEMINI,
            "live_model",
            lambda v: v or "models/gemini-3.1-flash-live-preview",
        ),
    }


def _outcome_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_OUTCOME_INGEST_PER_MIN": (
            settings.OUTCOME,
            "ingest_per_min",
            lambda v: int(v or "60"),
        ),
    }


def _ota_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_DEVICE_OTA_STATE_PATH": (settings.OTA, "state_path", lambda v: v or None),
    }


def _upload_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    return {
        "LIMA_UPLOAD_PER_MIN": (settings.UPLOAD, "per_min", lambda v: int(v or "30")),
        "LIMA_UPLOAD_TOKEN_SECRET": (settings.UPLOAD, "token_secret", lambda v: v or ""),
        "LIMA_UPLOAD_PUBLIC_GET": (
            settings.UPLOAD,
            "public_get_enabled",
            lambda v: _bool_env(v, frozenset({"1", "true", "yes"})),
        ),
        "LIMA_UPLOAD_TOKEN_TTL": (settings.UPLOAD, "token_ttl", lambda v: int(v or "86400")),
    }


def _integrations_map(settings: Any) -> dict[str, tuple[Any, str, Callable[[str | None], Any]]]:
    def _gitee_token(_value: str | None) -> str:
        return (os.environ.get("GITEE_TOKEN") or "").strip() or (
            os.environ.get("GITEE_ACCESS_TOKEN") or ""
        ).strip()

    return {
        "SUPABASE_URL": (settings.INTEGRATIONS, "supabase_url", _strip_or_empty),
        "SUPABASE_SECRET": (settings.INTEGRATIONS, "supabase_key", _strip_or_empty),
        "LANGSMITH_API_KEY": (settings.INTEGRATIONS, "langsmith_key", _strip_or_empty),
        "GITEE_TOKEN": (settings.INTEGRATIONS, "gitee_token", _gitee_token),
        "GITEE_ACCESS_TOKEN": (settings.INTEGRATIONS, "gitee_token", _gitee_token),
    }
