"""Intent detection helpers extracted from smart_router (CQ-014 slice 6)."""

from __future__ import annotations

import re

from backends import BACKENDS, THINKING_BACKENDS
from router_circuit_breaker import cb_allow

_THINKING_PATTERNS = [
    re.compile(r"仔细想想|深度分析|深入分析|深度思考|仔细分析|认真想|好好想|慢慢想", re.IGNORECASE),
    re.compile(r"逐步推理|一步一步|分步骤|详细推导|严格证明|严谨分析", re.IGNORECASE),
    re.compile(r"证明.*(?:定理|公式|等式|不等式|无理数|收敛|存在)", re.IGNORECASE),
    re.compile(r"数学证明|形式化证明|逻辑推导|归纳证明|反证法", re.IGNORECASE),
    re.compile(r"复杂度分析|时间复杂度|空间复杂度|算法.*证明", re.IGNORECASE),
    re.compile(r"系统架构.*设计|分布式.*设计|微服务.*拆分", re.IGNORECASE),
    re.compile(r"think carefully|think step by step|step by step|think harder", re.IGNORECASE),
    re.compile(r"prove that|formal proof|mathematical proof|rigorous proof", re.IGNORECASE),
    re.compile(r"deep analysis|in-depth analysis|thorough analysis", re.IGNORECASE),
    re.compile(r"multi.?step.*(?:reason|logic|problem)", re.IGNORECASE),
    re.compile(r"code architecture.*design|system design.*from scratch", re.IGNORECASE),
    re.compile(r"证明.*根号|证明.*√|prove.*sqrt|prove.*irrational", re.IGNORECASE),
    re.compile(r"求证|证明如下|请证明|帮我证明", re.IGNORECASE),
]


def detect_thinking_intent(query: str) -> bool:
    if not query:
        return False
    return any(pattern.search(query) for pattern in _THINKING_PATTERNS)


def get_thinking_backend() -> str:
    for name in THINKING_BACKENDS:
        if name in BACKENDS and BACKENDS[name].get("key") and cb_allow(name):
            return name
    # Fallback: first available thinking backend (even without circuit breaker)
    for name in THINKING_BACKENDS:
        if name in BACKENDS and BACKENDS[name].get("key"):
            return name
    return "scnet_ds_pro"  # safest default — always available
