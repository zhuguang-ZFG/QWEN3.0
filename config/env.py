"""Runtime environment-variable getters for routes/ modules (P1-2).

All values are now centralized in ``config.settings``; this module remains as a
thin facade so existing route imports keep working.
"""

from __future__ import annotations

import os

from config import backend_config
from config.settings import (
    DIGITAL_HUMAN,
    FLAGS,
    GEMINI,
    OTA,
    OUTCOME,
    SECURITY,
    UPLOAD,
    VOICE,
    DigitalHumanConfig,
)

# Re-export the digital-human dataclass for backward-compatible type hints.
__all__ = [
    "admin_token",
    "debug_enabled",
    "device_ota_state_path",
    "digital_human_config",
    "distill_log_enabled",
    "gfw_proxy",
    "gemini_live_model",
    "google_ai_key",
    "health_show_errors",
    "jina_api_key",
    "lima_api_key",
    "outcome_ingest_per_min",
    "public_demo_enabled",
    "public_demo_max_per_minute",
    "upload_per_min",
    "upload_public_get_enabled",
    "upload_token_secret",
    "upload_token_ttl",
    "voice_max_audio_bytes",
    "wechat_dev_login_enabled",
    "xiaozhi_compat_enabled",
    "xiaozhi_dev_static_login_code_enabled",
    "DigitalHumanConfig",
]


def admin_token() -> str:
    """LiMa admin token."""
    return SECURITY.admin_token


def lima_api_key() -> str:
    """Primary LiMa API key."""
    return SECURITY.api_key


def debug_enabled() -> bool:
    """Whether LIMA_DEBUG is set to ``1``."""
    return FLAGS.debug


def distill_log_enabled() -> bool:
    """Whether distill-queue logging is enabled."""
    return FLAGS.distill_log


def wechat_dev_login_enabled() -> bool:
    """WeChat dev-login bypass for device app auth."""
    return FLAGS.wechat_dev_login


def xiaozhi_dev_static_login_code_enabled() -> bool:
    """Static SMS verification code bypass in dev mode."""
    return FLAGS.xiaozhi_dev_static_login_code


def device_ota_state_path() -> str | None:
    """Path to OTA release-gate state file, if configured."""
    return OTA.state_path


def voice_max_audio_bytes() -> int:
    """Max decoded PCM bytes per audio chunk."""
    return VOICE.max_audio_bytes


def digital_human_config() -> DigitalHumanConfig:
    """Return digital-human asset directory and default connection values."""
    return DIGITAL_HUMAN


def jina_api_key() -> str:
    """Jina AI API key."""
    from config.settings import EMBEDDING

    return EMBEDDING.jina_api_key


def gfw_proxy() -> str:
    """Proxy for GFW egress."""
    from config.settings import EMBEDDING

    return EMBEDDING.gfw_proxy


def google_ai_key() -> str:
    """Google AI (Gemini) API key."""
    return backend_config.GOOGLE_AI_KEY


def gemini_live_model() -> str:
    """Gemini Live model identifier."""
    return GEMINI.live_model


def outcome_ingest_per_min() -> int:
    """Outcome-ingest rate limit per minute."""
    return OUTCOME.ingest_per_min


def public_demo_enabled() -> bool:
    """Whether the public demo chat endpoint is enabled."""
    return FLAGS.public_demo


def public_demo_max_per_minute() -> int:
    """Public demo per-client rate limit."""
    return FLAGS.public_demo_max_per_minute


def xiaozhi_compat_enabled() -> bool:
    """Whether the Xiaozhi v1 compatibility router is mounted."""
    return FLAGS.xiaozhi_compat


def health_show_errors() -> bool:
    """Expose startup errors in the health payload."""
    return FLAGS.health_show_errors


def upload_per_min() -> int:
    """Upload endpoint rate limit per minute."""
    return UPLOAD.per_min


def upload_token_secret() -> bytes:
    """HMAC secret for upload access tokens."""
    return UPLOAD.token_secret.encode()


def upload_public_get_enabled() -> bool:
    """Whether uploaded files are publicly readable without a token."""
    return UPLOAD.public_get_enabled


def upload_token_ttl() -> int:
    """Default TTL for upload access tokens, in seconds."""
    return UPLOAD.token_ttl
