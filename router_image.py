"""Image generation intent detection extracted from smart_router (CQ-014 slice 7)."""

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
    re.compile(
        r"^(please\s+)?(generate|draw|create|make)\s+(an?\s+)?(image|picture|photo)\s*(of\s+)?",
        re.IGNORECASE,
    ),
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
