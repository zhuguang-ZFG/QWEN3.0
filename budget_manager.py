"""
LiMa Budget Manager — 请求预算管理

每个后端设日请求限额，预防额度耗尽后的突然失败。
- 到达 warn_at (80%) 时降优先级
- 到达 100% 时自动下线
- 每日 UTC 0:00 自动重置
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional

# ── 预算配置 ─────────────────────────────────────────────────────────────────

@dataclass
class BudgetConfig:
    daily_limit: Optional[int]
    warn_at: float = 0.8


BACKEND_BUDGETS: dict[str, BudgetConfig] = {
    # LongCat 免费系列: 较宽松
    "longcat_lite": BudgetConfig(daily_limit=3000),
    "longcat_chat": BudgetConfig(daily_limit=3000),
    "longcat": BudgetConfig(daily_limit=2000),
    "longcat_thinking": BudgetConfig(daily_limit=1500),
    "longcat_omni": BudgetConfig(daily_limit=1500),
    "longcat_web": BudgetConfig(daily_limit=500),
    "longcat_web_think": BudgetConfig(daily_limit=300),
    "longcat_web_research": BudgetConfig(daily_limit=200),

    # NVIDIA 免费: 中等
    "nvidia_nemotron": BudgetConfig(daily_limit=1000),
    "nvidia_llama70b": BudgetConfig(daily_limit=1000),
    "nvidia_qwen_coder": BudgetConfig(daily_limit=1000),
    "nvidia_llama4": BudgetConfig(daily_limit=800),
    "nvidia_mistral": BudgetConfig(daily_limit=800),
    "nvidia_phi4": BudgetConfig(daily_limit=800),

    # OpenRouter 免费: 保守
    "or_deepseek_r1": BudgetConfig(daily_limit=500, warn_at=0.7),
    "or_qwen3_coder": BudgetConfig(daily_limit=500, warn_at=0.7),
    "or_llama70b": BudgetConfig(daily_limit=500, warn_at=0.7),
    "or_nemotron": BudgetConfig(daily_limit=500, warn_at=0.7),
    "or_qwen3_80b": BudgetConfig(daily_limit=500, warn_at=0.7),
    "or_nemotron120b": BudgetConfig(daily_limit=500, warn_at=0.7),

    # GitHub Models 免费: 保守
    "github_gpt4o": BudgetConfig(daily_limit=500, warn_at=0.7),
    "github_gpt4o_mini": BudgetConfig(daily_limit=500, warn_at=0.7),
    "github_llama70b": BudgetConfig(daily_limit=500, warn_at=0.7),
    "github_codestral": BudgetConfig(daily_limit=500, warn_at=0.7),

    # Google 免费: 宽松
    "google_flash_lite": BudgetConfig(daily_limit=1000, warn_at=0.8),
    "google_gemini3": BudgetConfig(daily_limit=1000, warn_at=0.8),
    "google_gemma4": BudgetConfig(daily_limit=1000, warn_at=0.8),

    # Groq 免费: 宽松
    "groq_llama4": BudgetConfig(daily_limit=1000, warn_at=0.8),
    "groq_gptoss": BudgetConfig(daily_limit=1000, warn_at=0.8),

    # SambaNova 免费: 保守
    "sambanova_ds_v3": BudgetConfig(daily_limit=500, warn_at=0.7),

    # Mistral 免费: 中等
    "mistral_small": BudgetConfig(daily_limit=800, warn_at=0.8),
    "mistral_medium": BudgetConfig(daily_limit=800, warn_at=0.8),
    "mistral_codestral": BudgetConfig(daily_limit=800, warn_at=0.8),

    # 中国移动: 保守
    "chinamobile": BudgetConfig(daily_limit=500, warn_at=0.7),

    # 逆向代理: 最保守
    "deepseek_free": BudgetConfig(daily_limit=200, warn_at=0.6),
}

from budget_cf_google import (  # noqa: E402
    CF_ACCOUNT_DAILY_LIMIT as CF_ACCOUNT_DAILY_LIMIT,
    CF_ACCOUNT_WARN_AT as CF_ACCOUNT_WARN_AT,
    CF_BACKEND_PREFIX,
    emit_budget_alerts,
    emit_cf_pool_alerts,
    get_cf_pool_status as get_cf_pool_status,
    get_cf_pool_usage as get_cf_pool_usage,
    get_total_requests_today as get_total_requests_today,
    get_usage_summary as get_usage_summary,
    register_cf_google_budgets,
)
from budget_gitee import register_gitee_budgets  # noqa: E402

register_cf_google_budgets(BACKEND_BUDGETS, BudgetConfig)
register_gitee_budgets(BACKEND_BUDGETS, BudgetConfig)

# ── 状态管理 ─────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_usage: dict[str, int] = {}
_reset_day: int = 0


def _check_reset():
    """每日 UTC 0:00 自动重置。"""
    global _reset_day
    today = int(time.time()) // 86400
    if today != _reset_day:
        _usage.clear()
        _reset_day = today


# ── 公开接口 ─────────────────────────────────────────────────────────────────

def record_usage(backend: str):
    """记录一次请求使用。"""
    with _lock:
        _check_reset()
        old_used = _usage.get(backend, 0)
        _usage[backend] = old_used + 1
        new_used = old_used + 1
    emit_budget_alerts(backend, old_used, new_used)
    if backend.startswith(CF_BACKEND_PREFIX):
        emit_cf_pool_alerts()


def is_budget_available(backend: str) -> bool:
    """预算是否还有余量。无配置的后端默认可用。"""
    cfg = BACKEND_BUDGETS.get(backend)
    if not cfg or cfg.daily_limit is None:
        return True
    with _lock:
        _check_reset()
        return _usage.get(backend, 0) < cfg.daily_limit


def get_budget_priority(backend: str) -> float:
    """返回 0-1 的预算优先级。越接近耗尽越低。无配置的返回 1.0。"""
    cfg = BACKEND_BUDGETS.get(backend)
    if not cfg or cfg.daily_limit is None:
        return 1.0
    with _lock:
        _check_reset()
        used = _usage.get(backend, 0)
    ratio = used / cfg.daily_limit
    return max(0.0, 1.0 - ratio)


def get_remaining_quota_score(backend: str) -> float:
    return get_budget_priority(backend)


def get_budget_status(backend: str) -> str:
    """返回: 'normal' | 'warning' | 'exhausted'"""
    cfg = BACKEND_BUDGETS.get(backend)
    if not cfg or cfg.daily_limit is None:
        return "normal"
    with _lock:
        _check_reset()
        used = _usage.get(backend, 0)
    ratio = used / cfg.daily_limit
    if ratio >= 1.0:
        return "exhausted"
    if ratio >= cfg.warn_at:
        return "warning"
    return "normal"


def get_all_budgets() -> dict[str, dict]:
    """返回所有后端的预算状态（供 /admin/api/stats 使用）。"""
    with _lock:
        _check_reset()
        result = {}
        for backend, cfg in BACKEND_BUDGETS.items():
            if cfg.daily_limit is None:
                continue
            used = _usage.get(backend, 0)
            result[backend] = {
                "used": used,
                "limit": cfg.daily_limit,
                "remaining": max(0, cfg.daily_limit - used),
                "status": get_budget_status(backend),
            }
        return result


# ── Cost class ──────────────────────────────────────────────────────────────────

# free = never block or count against quota
# limited = counted, warn_at 80%, block at 100%
# paid = never block (pay-as-you-go), just track
COST_CLASS: dict[str, str] = {}

# Local / free-tier backends
_LOCAL_BACKENDS = {
    "local_coder14b", "local_reasoning", "local_general",
    "local_fast", "local_chat", "local_qwen3", "local_phi4", "local_mistral",
    "deepseek_free",
}
_FREE_BACKENDS = {
    "chat_ubi", "llm7", "pollinations", "pollinations_openai",
    "pollinations_openai_large", "pollinations_deepseek", "pollinations_qwen_coder",
    "scnet_qwen30b", "scnet_qwen235b", "scnet_ds_flash", "scnet_ds_pro",
    "scnet_minimax",
    "ovh_llama70b", "ovh_deepseek",
    "cfai_llama70b", "cfai_llama4", "cfai_qwen_coder",
    "cfai_deepseek_r1", "cfai_mistral",
    "tele_reason", "tele_standard", "tele_apps",
    "assist_brainstorm", "vision_joycaption",
    "stock_gpt4o_mini", "stock_gemini_flash", "stock_deepseek",
    "stock_llama4", "stock_kimi_k2", "stock_glm46",
    "stock_qwen3_coder", "stock_news", "stock_mistral",
    "oldllm_gpt54", "oldllm_gpt53", "oldllm_gpt52", "oldllm_gpt51",
    "oldllm_gpt5", "oldllm_gpt5_mini", "oldllm_gpt41", "oldllm_gpt41_mini",
    "oldllm_gpt41_nano", "oldllm_gpt4", "oldllm_o1", "oldllm_o4_mini",
}


def _build_cost_class():
    for b in _LOCAL_BACKENDS:
        COST_CLASS[b] = "free"
    for b in _FREE_BACKENDS:
        COST_CLASS.setdefault(b, "free")


_build_cost_class()


def get_cost_class(backend: str) -> str:
    """free | limited | paid. Unknown backends default to 'paid' (conservative)."""
    return COST_CLASS.get(backend, "limited")


def should_track_cost(backend: str) -> bool:
    """Free/local backends never block on cost. Limited backends do."""
    return get_cost_class(backend) != "free"


# ── Token telemetry ─────────────────────────────────────────────────────────────

_token_lock = threading.Lock()
_token_usage: dict[str, dict] = {}


def record_token_usage(backend: str, prompt_tokens: int = 0,
                        completion_tokens: int = 0):
    """Best-effort token tracking from API response.usage."""
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return
    if not should_track_cost(backend):
        return
    with _token_lock:
        entry = _token_usage.setdefault(backend, {
            "prompt": 0, "completion": 0, "requests": 0,
        })
        entry["prompt"] += prompt_tokens
        entry["completion"] += completion_tokens
        entry["requests"] += 1

    # Emit token_usage_event to observability (M6-S3)
    try:
        from observability.metrics import record as _obs_record
        from observability.events import token_usage_event
        _obs_record(token_usage_event(backend, prompt_tokens, completion_tokens,
                                       get_cost_class(backend)))
    except ImportError:
        pass


def get_token_usage(backend: str = "") -> dict:
    """Return token telemetry. Pass empty string for all backends."""
    with _token_lock:
        if backend:
            return dict(_token_usage.get(backend, {"prompt": 0, "completion": 0, "requests": 0}))
        return {k: dict(v) for k, v in _token_usage.items()}


def reset_for_tests():
    with _lock:
        _usage.clear()
    with _token_lock:
        _token_usage.clear()


def set_usage_for_tests(backend: str, used: int):
    with _lock:
        _check_reset()
        _usage[backend] = used
