"""社区免费 API 后端定义（free_* 系列）"""

import logging
import os

from backends_registry._utils import legacy_free_enabled

logger = logging.getLogger(__name__)


# ── HTTPS-only community backends (always registered) ──
BACKENDS: dict[str, dict] = {
    # ── free_openai_next (社区分享, 500刀额度) ──
    "free_openai_next_gpt4": {
        "url": "https://api.openai-next.com/v1/chat/completions",
        "key": os.environ.get("FREE_OPENAI_NEXT_KEY", ""),
        "model": "gpt-4",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_openai_next_claude": {
        "url": "https://api.openai-next.com/v1/chat/completions",
        "key": os.environ.get("FREE_OPENAI_NEXT_KEY", ""),
        "model": "claude-3-5-sonnet-20241022",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_openai_next_deepseek": {
        "url": "https://api.openai-next.com/v1/chat/completions",
        "key": os.environ.get("FREE_OPENAI_NEXT_KEY", ""),
        "model": "deepseek-r1",
        "fmt": "openai",
        "timeout": 90,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    # ── free_centos (ai.centos.hk) ──
    "free_centos_gpt54": {
        "url": "https://ai.centos.hk/v1/chat/completions",
        "key": os.environ.get("FREE_CENTOS_KEY", ""),
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_centos_gpt55": {
        "url": "https://ai.centos.hk/v1/chat/completions",
        "key": os.environ.get("FREE_CENTOS_KEY", ""),
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    # ── free_muyuan (muyuan.do, 同 centos.hk 服务) ──
    "free_muyuan_gpt54": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_gpt55": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_gpt54_mini": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.4-mini",
        "fmt": "openai",
        "timeout": 30,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_codex": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "codex-auto-review",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_gpt55_compact": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.5-openai-compact",
        "fmt": "openai",
        "timeout": 60,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_gpt54_compact": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "gpt-5.4-openai-compact",
        "fmt": "openai",
        "timeout": 60,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_claude_haiku": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "claude-haiku-4-5-20251001",
        "fmt": "openai",
        "timeout": 30,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_claude_sonnet": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "claude-sonnet-4-6",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_muyuan_claude_opus": {
        "url": "https://muyuan.do/v1/chat/completions",
        "key": os.environ.get("FREE_MUYUAN_KEY", ""),
        "model": "claude-opus-4-8",
        "fmt": "openai",
        "timeout": 90,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

# ── HTTP-only community backends (opt-in, default disabled) ──
_AJIAKESI_ENABLED = legacy_free_enabled("AJIAKESI")
_TEAM_SPEED_ENABLED = legacy_free_enabled("TEAM_SPEED")

_AJIAKESI_BASE_URL = "http://codehub.ajiakesi.cn/v1/chat/completions"
_AJIAKESI_KEY = os.environ.get("FREE_AJIAKESI_KEY", "")
_AJIAKESI_BACKENDS = {
    "free_ajiakesi_gpt54": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.4",
        "fmt": "openai",
        "timeout": 60,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_ajiakesi_gpt55": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "caps": ["tool_calls"],
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_ajiakesi_gpt54_mini": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.4-mini",
        "fmt": "openai",
        "timeout": 30,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
    "free_ajiakesi_gpt55_compact": {
        "url": _AJIAKESI_BASE_URL,
        "key": _AJIAKESI_KEY,
        "model": "gpt-5.5-openai-compact",
        "fmt": "openai",
        "timeout": 60,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

_TEAM_SPEED_BASE_URL = "http://156.239.47.88:8080/v1/chat/completions"
_TEAM_SPEED_KEY = os.environ.get("FREE_TEAM_SPEED_KEY", "")
_TEAM_SPEED_BACKENDS = {
    "free_team_speed_gpt55": {
        "url": _TEAM_SPEED_BASE_URL,
        "key": _TEAM_SPEED_KEY,
        "model": "gpt-5.5",
        "fmt": "openai",
        "timeout": 90,
        "headers": {"User-Agent": "Mozilla/5.0"},
    },
}

if _AJIAKESI_ENABLED:
    BACKENDS.update(_AJIAKESI_BACKENDS)

if _TEAM_SPEED_ENABLED:
    BACKENDS.update(_TEAM_SPEED_BACKENDS)


def log_insecure_backend_status() -> None:
    """Emit warnings/info about opt-in cleartext backends at startup.

    Call this from server bootstrap after logging is configured.
    """
    if _AJIAKESI_ENABLED:
        logger.warning(
            "free_ajiakesi backends are enabled over cleartext HTTP; "
            "API keys, user messages, and any transmitted source code may be intercepted in transit"
        )
    else:
        logger.info(
            "free_ajiakesi backends are disabled by default; "
            "set LIMA_FREE_AJIAKESI_ENABLED=1 to opt in to cleartext HTTP endpoints"
        )

    if _TEAM_SPEED_ENABLED:
        logger.warning(
            "free_team_speed backends are enabled over cleartext HTTP; "
            "API keys and user messages may be intercepted in transit"
        )
    else:
        logger.info(
            "free_team_speed backends are disabled by default; "
            "set LIMA_FREE_TEAM_SPEED_ENABLED=1 to opt in to cleartext HTTP endpoints"
        )
