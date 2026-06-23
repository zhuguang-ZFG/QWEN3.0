"""Runtime environment-variable getters for routes/ modules (P1-2)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def admin_token() -> str:
    """LiMa admin token."""
    return os.environ.get("LIMA_ADMIN_TOKEN", "")


def lima_api_key() -> str:
    """Primary LiMa API key."""
    return os.environ.get("LIMA_API_KEY", "")


def debug_enabled() -> bool:
    """Whether LIMA_DEBUG is set to ``1``."""
    return os.environ.get("LIMA_DEBUG", "") == "1"


def distill_log_enabled() -> bool:
    """Whether distill-queue logging is enabled."""
    return os.environ.get("DISTILL_LOG", "0") == "1"


def wechat_dev_login_enabled() -> bool:
    """WeChat dev-login bypass for device app auth."""
    return os.environ.get("LIMA_XIAOZHI_WECHAT_DEV_LOGIN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def xiaozhi_dev_static_login_code_enabled() -> bool:
    """Static SMS verification code bypass in dev mode."""
    return os.environ.get("LIMA_XIAOZHI_DEV_STATIC_LOGIN_CODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def device_ota_state_path() -> str | None:
    """Path to OTA release-gate state file, if configured."""
    return os.environ.get("LIMA_DEVICE_OTA_STATE_PATH") or None


def voice_max_audio_bytes() -> int:
    """Max decoded PCM bytes per audio chunk."""
    return int(os.environ.get("LIMA_VOICE_MAX_AUDIO_BYTES", "1048576"))


@dataclass(frozen=True)
class DigitalHumanConfig:
    """Digital-human asset directory and default connection values."""

    directory: str = ""
    device_id: str = "web-tester"
    device_name: str = "LiMa 星云数字人"
    client_id: str = "web_test_client"
    wakeword_enabled: bool = False


def digital_human_config() -> DigitalHumanConfig:
    """Return digital-human asset directory and default connection values."""
    return DigitalHumanConfig(
        directory=os.environ.get("LIMA_DIGITAL_HUMAN_DIR", "").strip(),
        device_id=os.environ.get("LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_ID", "web-tester").strip(),
        device_name=os.environ.get(
            "LIMA_DIGITAL_HUMAN_DEFAULT_DEVICE_NAME", "LiMa 星云数字人"
        ).strip(),
        client_id=os.environ.get(
            "LIMA_DIGITAL_HUMAN_DEFAULT_CLIENT_ID", "web_test_client"
        ).strip(),
        wakeword_enabled=os.environ.get(
            "LIMA_DIGITAL_HUMAN_DEFAULT_WAKEUP_WORD_ENABLED", "false"
        ).strip().lower()
        == "true",
    )


def jina_api_key() -> str:
    """Jina AI API key."""
    return os.environ.get("JINA_API_KEY", "")


def gfw_proxy() -> str:
    """Proxy for GFW egress."""
    return os.environ.get("GFW_PROXY", "")


def google_ai_key() -> str:
    """Google AI (Gemini) API key."""
    return os.environ.get("GOOGLE_AI_KEY", "")


def gemini_live_model() -> str:
    """Gemini Live model identifier."""
    return os.environ.get(
        "LIMA_GEMINI_LIVE_MODEL", "models/gemini-3.1-flash-live-preview"
    )


def outcome_ingest_per_min() -> int:
    """Outcome-ingest rate limit per minute."""
    return int(os.environ.get("LIMA_OUTCOME_INGEST_PER_MIN", "60"))


def public_demo_enabled() -> bool:
    """Whether the public demo chat endpoint is enabled."""
    return os.environ.get("LIMA_PUBLIC_DEMO_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def public_demo_max_per_minute() -> int:
    """Public demo per-client rate limit."""
    raw = os.environ.get("LIMA_PUBLIC_DEMO_MAX_PER_MINUTE", "").strip()
    try:
        limit = int(raw) if raw else 6
    except ValueError:
        limit = 6
    return max(1, min(60, limit))


def xiaozhi_compat_enabled() -> bool:
    """Whether the Xiaozhi v1 compatibility router is mounted."""
    return os.environ.get("LIMA_XIAOZHI_COMPAT_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def health_show_errors() -> bool:
    """Expose startup errors in the health payload."""
    return os.environ.get("LIMA_HEALTH_SHOW_ERRORS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def upload_per_min() -> int:
    """Upload endpoint rate limit per minute."""
    return int(os.environ.get("LIMA_UPLOAD_PER_MIN", "30"))


def upload_token_secret() -> bytes:
    """HMAC secret for upload access tokens."""
    raw = os.environ.get("LIMA_UPLOAD_TOKEN_SECRET") or os.environ.get("LIMA_JWT_SECRET", "")
    return raw.encode()


def upload_public_get_enabled() -> bool:
    """Whether uploaded files are publicly readable without a token."""
    return os.environ.get("LIMA_UPLOAD_PUBLIC_GET", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def upload_token_ttl() -> int:
    """Default TTL for upload access tokens, in seconds."""
    return int(os.environ.get("LIMA_UPLOAD_TOKEN_TTL", "86400"))
