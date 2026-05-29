"""Backend tier tables and fallback routing for routes/quality_gate."""

from __future__ import annotations

BACKEND_TIERS = {
    "L1_free": [
        "longcat_lite",
        "longcat_chat",
        "longcat",
        "longcat_thinking",
        "longcat_omni",
        "chinamobile",
    ],
    "L2_nvidia": [
        "nvidia_qwen_coder",
        "nvidia_nemotron",
        "nvidia_phi4",
        "nvidia_llama4",
        "nvidia_llama70b",
        "nvidia_mistral",
    ],
    "L2_openrouter": [
        "or_deepseek_r1",
        "or_qwen3_coder",
        "or_llama70b",
        "or_nemotron",
        "or_qwen3_80b",
    ],
    "L3_paid": [],
}


def get_same_tier_backends(current_backend: str) -> list:
    """Return other backends in the same tier."""
    for _tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            return [backend for backend in backends if backend != current_backend]
    return []


def get_upgrade_chain(current_backend: str) -> list:
    """Return backends from higher tiers, preserving tier order."""
    tiers = list(BACKEND_TIERS.keys())
    current_tier = None
    for tier, backends in BACKEND_TIERS.items():
        if current_backend in backends:
            current_tier = tier
            break
    if not current_tier:
        return ["longcat_chat"]
    tier_idx = tiers.index(current_tier)
    upgrade_backends = []
    for tier in tiers[tier_idx + 1:]:
        upgrade_backends.extend(BACKEND_TIERS[tier][:2])
    return upgrade_backends


def default_route(query: str, ide: str = "unknown") -> str:
    """Fallback route when router output is invalid."""
    del ide
    query_len = len(query)
    if query_len < 50:
        return "longcat_lite"
    code_keywords = [
        "\u4ee3\u7801",
        "code",
        "\u51fd\u6570",
        "function",
        "bug",
        "error",
        "def ",
        "class ",
        "import ",
    ]
    if any(keyword in query.lower() for keyword in code_keywords):
        return "nvidia_qwen_coder"
    if query_len > 200:
        return "longcat"
    return "longcat_chat"
