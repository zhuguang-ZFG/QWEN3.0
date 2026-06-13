"""Intent detection helpers (migrated from legacy router_intent/router_image)."""
from __future__ import annotations

import re

_IMAGE_PATTERNS = [
    re.compile(r"画一[个只张幅副]", re.IGNORECASE),
    re.compile(r"画个", re.IGNORECASE),
    re.compile(r"生成.*图", re.IGNORECASE),
    re.compile(r"画.*图", re.IGNORECASE),
    re.compile(r"设计.*logo", re.IGNORECASE),
    re.compile(r"generate.*image", re.IGNORECASE),
    re.compile(r"\bdraw\b", re.IGNORECASE),
    re.compile(r"create.*picture", re.IGNORECASE),
    re.compile(r"画.*画", re.IGNORECASE),
    re.compile(r"帮我画", re.IGNORECASE),
    re.compile(r"给我画", re.IGNORECASE),
    re.compile(r"生成.*照片", re.IGNORECASE),
    re.compile(r"生成.*插画", re.IGNORECASE),
    re.compile(r"make.*image", re.IGNORECASE),
]

_IMAGE_STRIP_PATTERNS = [
    re.compile(r"^(请|帮我|给我|帮忙)?(画一[个只张幅副]|画个|画一下|画)"),
    re.compile(r"^(请|帮我|给我)?生成(一[张幅副])?(.*?)(图片?|图像|照片|插画)的?"),
    re.compile(r"^(请|帮我|给我)?设计(一个)?"),
    re.compile(r"^(请|帮我|给我)?(create|generate|make)\s+(a\s+)?(picture|image|photo)\s+of\s*"),
    re.compile(r"^(请|帮我|给我)?draw\s+"),
]

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


def detect_image_intent(query: str) -> tuple[bool, str]:
    """Return (is_image_request, pollinations_prompt)."""
    if not query:
        return (False, "")

    is_image = any(pattern.search(query) for pattern in _IMAGE_PATTERNS)
    if not is_image:
        return (False, "")

    prompt = query.strip()
    for strip_pat in _IMAGE_STRIP_PATTERNS:
        prompt = strip_pat.sub("", prompt).strip()

    if not prompt or len(prompt) < 2:
        prompt = query.strip()

    prompt = re.sub(r"[。！？.!?]+$", "", prompt).strip()

    if re.search(r"[一-鿿]", prompt):
        prompt = f"high quality, detailed, {prompt}"

    return (True, prompt)


def detect_thinking_intent(query: str) -> bool:
    """Detect requests that ask for step-by-step or deep reasoning."""
    if not query:
        return False
    return any(pattern.search(query) for pattern in _THINKING_PATTERNS)
