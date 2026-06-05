"""dynamic_backend_pool.py — 动态后端池：基于历史质量数据替代硬编码 POOLS。

Four-tier pool system:
  - generate  极速初版生成（超时 3s，优先 Groq/Cerebras/SCNet 免费线）
  - review    代码审查（中等推理，SCNet DeepSeek / GitHub Codestral）
  - refine    精修复（编码专精，Cloudflare Qwen Coder / NVIDIA Qwen Coder）
  - fallback  全量回退池（所有可用后端，最后手段）

Each pool is:
  1. Sorted by coding_backend_scorer quality weights
  2. Filtered by health (no cooldown/circuit-broken backends)
  3. Refreshed per-request or cached with TTL (default 60s)
"""

from __future__ import annotations

import logging
import random
import time
from collections import defaultdict

import health_tracker

_log = logging.getLogger(__name__)

# ── Static base pools (used when coding_backend_scorer is unavailable) ──────

_GENERATE_POOL_BASE = [
    # Ultra-fast: <2s typical, low context
    "groq_llama70b", "cerebras_gptoss", "groq_gptoss",
    "groq_gptoss_20b", "groq_qwen32b", "groq_llama4",
    "scnet_qwen30b", "scnet_ds_flash",
    # Fallback fast
    "mistral_small", "cf_llama70b", "cf_qwen3_30b",
    "google_flash_lite", "github_gpt4o_mini",
]

_REVIEW_POOL_BASE = [
    # Medium reasoning: need to evaluate code quality
    "scnet_ds_flash", "scnet_qwen235b", "scnet_ds_pro",
    "scnet_qwen30b",
    "github_gpt4o_mini", "github_codestral",
    "cf_qwen_coder", "cfai_qwen_coder",
    "cf_deepseek_r1", "cfai_deepseek_r1",
    "cf_gptoss_120b", "cfai_llama70b",
    "mistral_large", "mistral_devstral",
    "cerebras_gptoss", "groq_llama70b",
]

_REFINE_POOL_BASE = [
    # Code-specialized: need precise code edits
    "cf_qwen_coder", "cfai_qwen_coder",
    "scnet_ds_flash", "scnet_ds_pro",
    "scnet_qwen235b",
    "github_codestral", "github_gpt4o_mini",
    "nvidia_qwen35_coder", "nvidia_deepseek_v4",
    "nvidia_qwen_coder",
    "mistral_codestral", "mistral_devstral",
    "or_qwen3_coder", "or_gptoss_120b",
    "cf_kimi_k26", "kimi",
]

_FALLBACK_POOL_BASE = [
    # Everything else — broad coverage
    "scnet_ds_flash", "scnet_qwen30b", "scnet_qwen235b",
    "scnet_ds_pro", "scnet_large_ds_flash",
    "github_gpt4o", "github_gpt4o_mini", "github_codestral",
    "github_deepseek_r1", "github_llama70b",
    "cf_qwen_coder", "cfai_qwen_coder", "cf_gptoss_120b",
    "cf_deepseek_r1", "cfai_deepseek_r1", "cfai_llama70b",
    "cf_qwen3_30b", "cf_mistral", "cf_kimi_k26",
    "groq_llama70b", "groq_gptoss", "cerebras_gptoss",
    "mistral_large", "mistral_small", "mistral_devstral",
    "nvidia_qwen35_coder", "nvidia_deepseek_v4",
    "google_flash", "google_flash_lite", "google_pro",
    "deepinfra_qwen235b", "deepinfra_llama4",
    "sambanova_ds_v3", "sambanova_llama4",
    "or_gptoss_120b", "or_qwen3_coder",
    "fireworks_llama405b",
    "chinamobile",
]


# ── Cache ────────────────────────────────────────────────────────────────────

_cache: dict[str, list[str]] = {}
_cache_ts: float = 0
CACHE_TTL_SEC = 60  # Refresh pool rankings every 60s


def _load_scorer_weights() -> dict[str, float]:
    """Load coding quality weights from scorer, return {backend: weight}."""
    try:
        from coding_backend_scorer import _load_scores
        return _load_scores()
    except (ImportError, Exception) as e:
        _log.debug("coding_backend_scorer unavailable: %s", type(e).__name__)
        return {}


def _is_selectable(name: str) -> bool:
    """Check if backend is healthy enough for selection."""
    if health_tracker.is_cooled_down(name):
        return False
    state = health_tracker.get_backend_state(name)
    # Reject known-bad states
    if state and hasattr(state, "status"):
        status = getattr(state, "status", "")
        if status in ("dead", "disabled"):
            return False
    return True


def _sort_by_quality(pool: list[str], weights: dict[str, float]) -> list[str]:
    """Sort backend list by quality weight (highest first), shuffle within tiers."""
    if not weights:
        # No scorer data: shuffle to spread load
        shuffled = list(pool)
        random.shuffle(shuffled)
        return shuffled

    # Group by weight tier for rotation within tiers
    tiers: dict[int, list[str]] = defaultdict(list)
    for name in pool:
        w = weights.get(name, 1.0)
        if w >= 1.3:
            tier = 0  # proven
        elif w >= 1.0:
            tier = 1  # good
        elif w >= 0.7:
            tier = 2  # adequate
        else:
            tier = 3  # unknown/weak
        tiers[tier].append(name)

    result = []
    for tier in sorted(tiers.keys()):
        shuffled = tiers[tier][:]
        random.shuffle(shuffled)
        result.extend(shuffled)

    return result


def _build_pool(base: list[str], max_count: int = 8) -> list[str]:
    """Build a pool: scorer-sort → health-filter → take max_count."""
    weights = _load_scorer_weights()
    sorted_pool = _sort_by_quality(base, weights)
    healthy = [b for b in sorted_pool if _is_selectable(b)]
    return healthy[:max_count]


def get_pool(pool_name: str, max_count: int = 8) -> list[str]:
    """Get a dynamic backend pool by name (cached with TTL)."""
    global _cache, _cache_ts

    now = time.time()
    if _cache and (now - _cache_ts) < CACHE_TTL_SEC:
        cached = _cache.get(pool_name)
        if cached:
            return cached

    base_map = {
        "generate": _GENERATE_POOL_BASE,
        "review": _REVIEW_POOL_BASE,
        "refine": _REFINE_POOL_BASE,
        "fallback": _FALLBACK_POOL_BASE,
    }

    base = base_map.get(pool_name, _FALLBACK_POOL_BASE)
    pool = _build_pool(base, max_count)

    if not pool:
        # Emergency: return base unfiltered (health check might be too aggressive)
        _log.warning("Pool '%s' empty after filtering, returning raw base", pool_name)
        pool = base[:max_count]

    _cache[pool_name] = pool
    _cache_ts = now
    return pool


def get_multi_pass_pools() -> dict[str, list[str]]:
    """Get all pools needed for multi-pass refinement pipeline."""
    return {
        "generate": get_pool("generate", 5),
        "review": get_pool("review", 5),
        "refine": get_pool("refine", 5),
        "fallback": get_pool("fallback", 10),
    }


def get_orchestrator_pools() -> dict[str, list[str]]:
    """Get tiered pools for code_orchestrator compatibility.

    Maps to the existing POOLS dict structure:
      - fast: for simple tasks
      - coder: for standard coding
      - strong: for complex coding
    """
    return {
        "fast": get_pool("generate", 7),
        "coder": get_pool("review", 8),
        "strong": get_pool("refine", 8),
    }


def refresh() -> None:
    """Force refresh all pools (clear cache)."""
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = 0
