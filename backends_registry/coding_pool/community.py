"""Coding-pool backend definitions: community."""

import logging
import os

logger = logging.getLogger(__name__)


def _is_truthy(value: str | None) -> bool:
    """Check whether an env-var value means 'enabled'."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


BACKENDS: dict[str, dict] = {
    "free_muyuan_gpt54_code": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_gpt55_code": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_codex_code": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "codex-auto-review",
        "fmt": "openai",
        "timeout": 60,
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
        "caps": ["tool_calls", "code"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

# ── HTTP-only community backends (opt-in, default disabled) ──
_AJIAKESI_ENABLED = _is_truthy(os.environ.get("FREE_AJIAKESI_ENABLED"))
_AJIAKESI_BASE_URL = "http://codehub.ajiakesi.cn/v1/chat/completions"
_AJIAKESI_KEY = os.environ.get("FREE_AJIAKESI_KEY", "")
_AJIAKESI_CODE_BACKENDS = {
    "free_ajiakesi_gpt54_code": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_ajiakesi_gpt55_code": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "admission": "code_medium_candidate",
        "private_code_allowed": True,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

if _AJIAKESI_ENABLED:
    BACKENDS.update(_AJIAKESI_CODE_BACKENDS)
    logger.warning(
        "free_ajiakesi_code backends are enabled over cleartext HTTP; "
        "API keys and user messages may be intercepted in transit"
    )
else:
    logger.info(
        "free_ajiakesi_code backends are disabled by default; "
        "set FREE_AJIAKESI_ENABLED=1 to opt in to cleartext HTTP endpoints"
    )
