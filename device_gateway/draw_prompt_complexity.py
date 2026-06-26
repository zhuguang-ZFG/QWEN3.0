"""Complexity classification and simplification for plotter drawing prompts."""

from __future__ import annotations

import re
from typing import Any

from device_gateway.device_profile.registry import get_device_profile

_COMPLEXITY_HIGH_SIGNALS = frozenset(
    {
        "照片",
        "photorealistic",
        "3d",
        "三维",
        "立体",
        "透视",
        "阴影",
        "shadow",
        "渐变",
        "gradient",
        "填充",
        "fill",
        "涂色",
        "coloring",
        "上色",
        "纹理",
        "texture",
        "毛发",
        "fur",
        "羽毛",
        "树叶",
        "叶子",
        "人群",
        "建筑",
        "城市",
        "风景",
        "山水",
        "复杂",
        "complicated",
        "detailed",
        "超精细",
        "大量",
        "many",
        "多个",
        "多个人",
        "背景",
        "background",
        "场景",
        "油画",
        "水彩",
        "素描",
        "sketch",
        "写实",
        "realistic",
        "肖像",
        "portrait",
        "人脸",
    }
)
_COMPLEXITY_MEDIUM_SIGNALS = frozenset(
    {
        "树",
        "花",
        "动物",
        "房子",
        "车",
        "飞机",
        "船",
        "机器人",
        "卡通",
        "cartoon",
        "表情",
        "细节",
        "some details",
        "small",
        "小",
    }
)

# 简化提示词时需要剥离的修饰词/短语
_SIMPLIFICATION_REMOVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(彩色的|红色的|蓝色的|绿色的|黄色的|黑色的|白色的|灰色的|[\u4e00-\u9fa5]{1,3}色的)"),
    re.compile(r"(毛茸茸的|光滑的|金属的|木质的|玻璃的|塑料的)"),
    re.compile(r"(在阳光下|在月光下|在雨中|在雪地里|在森林里|在草原上|在城市里|在海边)"),
    re.compile(r"(戴着|穿着|拿着|抱着|旁边有|周围有|背景有)"),
    re.compile(r"(很多|许多|大量|一群|一排|一片|满屏)"),
    re.compile(r"(逼真的|写实的|3d的|立体的|透视的|阴影的|渐变的)"),
]


def classify_plotter_complexity(prompt: str) -> str:
    """根据关键词将用户描述分级为 simple / medium / complex。"""
    text = (prompt or "").lower()
    high_hits = sum(1 for signal in _COMPLEXITY_HIGH_SIGNALS if signal in text)
    medium_hits = sum(1 for signal in _COMPLEXITY_MEDIUM_SIGNALS if signal in text)
    if high_hits >= 1:
        return "complex"
    if medium_hits >= 1:
        return "medium"
    return "simple"


def _max_complexity_for_profile(profile) -> str:
    """根据设备最大路径点数决定可接受复杂度。"""
    if profile is None:
        return "simple"
    points = profile.max_path_points
    if points <= 60:
        return "simple"
    if points <= 150:
        return "medium"
    return "complex"


def simplify_prompt_for_plotter(prompt: str) -> str:
    """用启发式规则把复杂描述压缩为单一主体简笔画描述。"""
    simplified = prompt or "简单图形"
    for pattern in _SIMPLIFICATION_REMOVE_PATTERNS:
        simplified = pattern.sub("", simplified)
    for sep in (",", "，", "和", "与", "还有", "以及"):
        if sep in simplified:
            simplified = simplified.split(sep)[0]
            break
    simplified = re.sub(r"(在|从|到|位于).{0,10}(上|下|里|中|前面|后面|旁边)", "", simplified)
    simplified = re.sub(r"^画(一个|个|出|入)?", "", simplified).strip()
    core = simplified[:20].strip() or "简单图形"
    return f"简笔画：{core}"


def screen_drawing_request(user_prompt: str, device_id: str | None = None) -> dict[str, Any]:
    """预审用户请求：判断是否超出当前笔绘机能力，并给出简化建议。"""
    profile = get_device_profile(device_id) if device_id else None
    complexity = classify_plotter_complexity(user_prompt)
    max_allowed = _max_complexity_for_profile(profile)
    rank = {"simple": 0, "medium": 1, "complex": 2}
    if rank[complexity] > rank[max_allowed]:
        simplified = simplify_prompt_for_plotter(user_prompt)
        return {
            "feasible": False,
            "complexity": complexity,
            "max_allowed": max_allowed,
            "simplified_prompt": simplified,
            "reason": f"描述过于复杂（{complexity}），超出设备能力（{max_allowed}）",
            "suggestion": f"这个描述对笔绘机太难了。建议简化为：{simplified}",
        }
    return {
        "feasible": True,
        "complexity": complexity,
        "max_allowed": max_allowed,
        "simplified_prompt": user_prompt,
        "reason": "",
        "suggestion": "",
    }
