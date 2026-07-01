# coding capability retired v3.0，但本模块的 AFFINITY/classify_complexity/get_affinity_backends
# 仍被 speculative.py（请求流水线推测执行）和 context_pipeline/complexity.py 使用，未退役。
"""Speculative execution policy: complexity classification and backend affinity."""

from __future__ import annotations

import random

AFFINITY = {
    "simple_fast": [
        "longcat_lite",
        "longcat_chat",
        "google_flash",
        "groq_llama70b",
        "cerebras_gptoss",
        "cf_llama70b",
        "cf_qwen3_30b",
        "cf_gemma4",
        "ovh_llama70b",
        "groq_qwen32b",
        "nvidia_nemotron",
        "nvidia_llama70b",
        "sambanova_llama4",
        "deepinfra_llama4",
        "groq_llama4",
        "groq_gptoss",
        "google_flash_lite",
        "google_gemma4",
        "github_gpt4o_mini",
    ],
    "complex_premium": [
        "longcat",
        "longcat_thinking",
        "fireworks_llama405b",
        "cf_kimi_k26",
        "mistral_large",
        "nvidia_qwen_coder",
    ],
}

_COMPLEX_KEYWORDS = [
    "refactor",
    "architecture",
    "migrate",
    "redesign",
    "concurrent",
    "distributed",
    "optimize",
    "performance",
]


def _extract_user_text(messages: list[dict]) -> str:
    """Extract all user text from messages."""
    parts = []
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
    return " ".join(parts)


def score_request(messages: list[dict], ide: str = "") -> tuple[int, dict[str, str]]:
    """Unified request complexity scoring.

    Returns a score (1-10) and a dict of detected factor labels.
    This is the single source of truth used by both the speculative
    execution path and the legacy ComplexityAssessment facade.
    """
    user_text = _extract_user_text(messages)
    factors: dict[str, str] = {}
    score = 0

    char_count = len(user_text)
    if char_count >= 4000:
        factors["long_input"] = str(char_count)
        score += 3
    elif char_count >= 1500:
        factors["medium_input"] = str(char_count)
        score += 1

    lowered = user_text.lower()
    kw_hits = sum(1 for kw in _COMPLEX_KEYWORDS if kw in lowered)
    if kw_hits >= 2:
        factors["complex_task"] = str(kw_hits)
        score += 2
    elif kw_hits >= 1:
        factors["moderate_task"] = str(kw_hits)
        score += 1

    if ide:
        score += 1
        factors["ide_present"] = ide

    return min(score, 10), factors


def classify_complexity(query: str, messages: list[dict]) -> str:
    """Return 'simple' | 'complex' for routing strategy selection."""
    score, _ = score_request(messages)
    if score >= 5:
        return "complex"
    return "simple"


def get_affinity_backends(complexity: str) -> list[str]:
    """Return shuffled backend pool for the given complexity tier."""
    try:
        import capability_matrix

        intent = {
            "simple": "english",
            "complex": "reasoning",
        }.get(complexity, "english")
        pool = capability_matrix.select_backends(intent, top_n=12)
    except Exception:
        if complexity == "simple":
            pool = list(AFFINITY["simple_fast"])
        else:
            pool = list(AFFINITY["complex_premium"])
    random.shuffle(pool)
    return pool
