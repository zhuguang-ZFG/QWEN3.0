"""Coding-pool backend definitions: community."""

import logging

from backends_registry._utils import legacy_free_enabled
from config.backend_config import FREE_AJIAKESI_KEY, FREE_MUYUAN_KEY

logger = logging.getLogger(__name__)


BACKENDS: dict[str, dict] = {
    "free_muyuan_gpt54_code": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": FREE_MUYUAN_KEY,
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
        "key": FREE_MUYUAN_KEY,
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
        "key": FREE_MUYUAN_KEY,
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
_AJIAKESI_ENABLED = legacy_free_enabled("AJIAKESI")
_AJIAKESI_BASE_URL = "http://codehub.ajiakesi.cn/v1/chat/completions"
_AJIAKESI_KEY = FREE_AJIAKESI_KEY
_AJIAKESI_CODE_BACKENDS = {
    "free_ajiakesi_gpt54_code": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "admission": "code_medium_candidate",
        # Private source code must not traverse cleartext HTTP.
        "private_code_allowed": False,
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
        # Private source code must not traverse cleartext HTTP.
        "private_code_allowed": False,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

if _AJIAKESI_ENABLED:
    BACKENDS.update(_AJIAKESI_CODE_BACKENDS)


def log_insecure_backend_status() -> None:
    """Emit warnings/info about opt-in cleartext backends at startup.

    Call this from server bootstrap after logging is configured.
    """
    if _AJIAKESI_ENABLED:
        logger.warning(
            "free_ajiakesi_code backends are enabled over cleartext HTTP; "
            "API keys, user messages, and public code prompts may be intercepted in transit "
            "(private source code is blocked by private_code_allowed=False)"
        )
    else:
        logger.info(
            "free_ajiakesi_code backends are disabled by default; "
            "set LIMA_FREE_AJIAKESI_ENABLED=1 to opt in to cleartext HTTP endpoints"
        )
