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

# ── 状态管理 ─────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_usage: dict[str, int] = {}
_reset_day: int = 0


def _check_reset():
    """每日 UTC 0:00 自动重置。"""
    global _reset_day
    today = int(time.time()) // 86400
    if today != _reset_day:
        _reset_day = today
        _usage.clear()


# ── 公开接口 ─────────────────────────────────────────────────────────────────

def record_usage(backend: str):
    """记录一次请求使用。"""
    with _lock:
        _check_reset()
        _usage[backend] = _usage.get(backend, 0) + 1


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


def reset_for_tests():
    with _lock:
        _usage.clear()


def set_usage_for_tests(backend: str, used: int):
    with _lock:
        _check_reset()
        _usage[backend] = used
