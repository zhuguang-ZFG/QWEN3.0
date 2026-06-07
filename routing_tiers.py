"""Model tier definitions for cost-aware routing.

Tiers:
  FREE    — no API key cost, suitable for simple tasks (difficulty 0-30)
  BUDGET  — low-cost, good for everyday coding (difficulty 30-70)
  PREMIUM — high-capability, reserved for complex tasks (difficulty 70-100)
"""

from __future__ import annotations

# Backend → tier mapping
FREE_BACKENDS: set[str] = {
    "chinamobile",  # MiniMax M25, free
    "longcat_chat",  # LongCat, free tier
    "longcat_lite",
    "ddg_gpt4o_mini",  # DuckDuckGo (if available)
    "github_gpt4o_mini",  # GitHub Copilot free
}

BUDGET_BACKENDS: set[str] = {
    "groq_llama8b",
    "groq_llama70b",
    "groq_gptoss",
    "groq_gptoss_20b",
    "groq_llama4",
    "cerebras_llama8b",
    "cerebras_gptoss",
    "mistral_small",
    "scnet_qwen30b",
    "scnet_ds_flash",
}

PREMIUM_BACKENDS: set[str] = {
    "scnet_ds_pro",
    "scnet_qwen235b",
    "groq_qwen32b",
    "mistral_large",
    "mistral_devstral",
    "github_gpt4o",
    "github_codestral",
    "cerebras_qwen235b",
    "hermes_agent",  # Agent execution (special)
    "kimi",
    "cf_kimi_k26",
    "cf_deepseek_r1",
    "cfai_deepseek_r1",
    "cf_qwen_coder",
    "cfai_qwen_coder",
    "nvidia_qwen35_coder",
    "nvidia_deepseek_v4",
}

# Any backend not in these sets defaults to BUDGET tier
DEFAULT_TIER = "budget"


def get_tier(backend_name: str) -> str:
    """Return tier name for a backend."""
    if backend_name in FREE_BACKENDS:
        return "free"
    if backend_name in PREMIUM_BACKENDS:
        return "premium"
    if backend_name in BUDGET_BACKENDS:
        return "budget"
    return DEFAULT_TIER


def tier_for_difficulty(difficulty: int) -> str:
    """Map difficulty score (0-100) to target tier."""
    if difficulty <= 30:
        return "free"
    if difficulty <= 70:
        return "budget"
    return "premium"
