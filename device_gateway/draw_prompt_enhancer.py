"""Prompt enhancer for pen-plotter drawing generation.

Translates free-form user descriptions into a constrained prompt tuned for
Wanx / image-to-SVG / pen-plotter execution:
- black lines only, pure white background
- minimal line count, single-stroke / closed-contour hints for vectorization
- vectorization-friendly spacing (no fixed px stroke width)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from device_gateway.device_profile.models import DeviceProfile
from device_gateway.device_profile.registry import get_device_profile
from device_gateway.draw_prompt_few_shot import PLOTTER_FEW_SHOT

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "你是 LiMa 绘图助手，专为 ESP32 笔绘机/写字机生成可执行的简笔画指令。"
    "设备只有一支笔，只能画黑色线条，不能上色、不能涂阴影、不能表现颜色/渐变/纹理。"
    "【绝对禁止】彩色、灰度、阴影、渐变、填充、文字、照片写实、"
    "多主体复杂场景、3D透视、细密毛发/树叶/人群/建筑。"
    "【必须遵守】纯黑白线条图，纯白背景，无文字；只画单一主体或极简构图；"
    "线条连续、封闭图形完全闭合，线条间距≥5px，主体居中占画面60-80%；"
    "用最少线条表达特征，避免交叉线、虚线、点阵、装饰性背景。"
    "【失败处理】如果用户描述超出能力，主动建议简化，不要勉强生成。"
    "【自检】生成前问自己：这个图能用单支笔一笔一笔描出来吗？"
)

CAPABILITY_PROMPT_MAP = {
    "esp32_xy_plotter": (
        "设备能力：XY平台单笔画绘制，支持G-code，不支持颜色填充。线条粗细固定，请在设计中注意线条密度避免卡笔。"
    ),
    "esp32_writing_machine": ("设备能力：中文汉字书写，支持多种字体，可连续书写多行。注意汉字笔画顺序和连笔处理。"),
}

COMPLEXITY_STROKES = {
    "低": "约10笔画",
    "中": "约20笔画",
    "高": "约40笔画",
}

_REFINEMENT_RE = re.compile(r"再|大一点|小一点|改成|同样|还是|加点|减少|更.*一点|改.*黑白")

_WRITING_HINTS = ("writing", "write", "u8", "写字", "书写机")
_PLOTTER_HINTS = ("plotter", "xy", "draw", "u1", "笔绘")


def _apply_refinement_hint(user_prompt: str, conversation_context: str) -> str:
    if not conversation_context or not _REFINEMENT_RE.search(user_prompt):
        return user_prompt
    return f"基于上一轮，{user_prompt}"


def _build_style_hint(style: str, medium: str) -> str:
    """Build a style description hint string.

    Args:
        style: drawing style (e.g. 简约, 可爱, 写实轮廓).
        medium: medium description string (e.g. "中复杂度（约20笔画）").

    Returns:
        Combined style hint string.
    """
    return f"{style}风格，{medium}"


def _build_subject_expansion(subject: str) -> str:
    """Wrap a subject into a drawing instruction fragment.

    Args:
        subject: the user's subject/prompt.

    Returns:
        Subject expansion string like "画一个{subject}的简笔画".
    """
    return f"画一个{subject}的简笔画"


def _normalize_user_prompt(user_prompt: str, conversation_context: str) -> str:
    """Ensure *user_prompt* is a non-empty string, applying refinement hints."""
    if not isinstance(user_prompt, str):
        user_prompt = str(user_prompt)
    user_prompt = user_prompt.strip()
    if not user_prompt:
        user_prompt = "一个简单图形"
    return _apply_refinement_hint(user_prompt, conversation_context)


def _device_constraint_line(profile: DeviceProfile | None) -> str:
    """根据设备 profile 生成能力约束句。"""
    if profile is None:
        return "设备约束：工作区约100x100mm，路径点数尽量控制在100以内。"
    workspace = profile.workspace_mm
    return (
        f"设备约束：工作区{workspace.get('x', 100):.0f}x{workspace.get('y', 100):.0f}mm，"
        f"路径点数尽量控制在{profile.max_path_points}以内。"
    )


def _assemble_instruction_parts(
    device_type: str,
    conversation_context: str,
    previous_failed_prompts: list[str] | None,
    device_profile: DeviceProfile | None,
) -> list[str]:
    """Build the ordered list of system/capability/retry instruction fragments."""
    parts = [SYSTEM_INSTRUCTION, PLOTTER_FEW_SHOT]
    if conversation_context:
        parts.append(f"【对话上下文】{conversation_context}")

    capability = CAPABILITY_PROMPT_MAP.get(device_type, "")
    if capability:
        parts.append(capability)

    parts.append(_device_constraint_line(device_profile))

    if previous_failed_prompts:
        parts.append(f"注意：之前以下描述生成失败，请调整：{previous_failed_prompts[-1]}")

    return parts


def enhance_drawing_prompt(
    user_prompt: str,
    *,
    style: str = "简约",
    complexity: str = "中",
    device_type: str = "esp32_xy_plotter",
    previous_failed_prompts: list[str] | None = None,
    conversation_context: str = "",
    device_profile: DeviceProfile | None = None,
) -> str:
    """Wrap a user description with pen-plotter constraints.

    Args:
        user_prompt: raw user description, e.g. "画一只猫".
        style: one of 简约 / 可爱 / 写实轮廓.
        complexity: one of 低 / 中 / 高.
        device_type: device profile key in CAPABILITY_PROMPT_MAP.
        previous_failed_prompts: prior prompts that failed generation/vectorization.
        conversation_context: recent successful/failed draw turns for this device.
        device_profile: optional device profile for injecting workspace/point limits.

    Returns:
        A constrained prompt ready for the image generation backend.
    """
    user_prompt = _normalize_user_prompt(user_prompt, conversation_context)
    strokes = COMPLEXITY_STROKES.get(complexity, COMPLEXITY_STROKES["中"])
    medium_desc = f"{complexity}复杂度（{strokes}）"

    prefix = "。".join(
        _assemble_instruction_parts(device_type, conversation_context, previous_failed_prompts, device_profile)
    )
    return (
        f"{prefix}。"
        f"{_build_subject_expansion(user_prompt)}，"
        f"{_build_style_hint(style, medium_desc)}，"
        "纯黑白线条图，纯白背景，无文字。"
    )


from device_gateway.draw_prompt_memory import (  # noqa: F401 (re-exports for backward compat)
    get_draw_conversation_context,
    get_failed_draw_prompts,
    record_device_draw_turn,
    record_failed_draw_prompt,
    reset_draw_prompt_history_for_tests,
)


from device_gateway.draw_prompt_complexity import (  # noqa: F401 (re-exports)
    classify_plotter_complexity,
    screen_drawing_request,
    simplify_prompt_for_plotter,
)


def resolve_device_type(device_id: str | None, prefs: dict) -> str:
    """Map device profile / prefs to draw_prompt_enhancer device_type key."""
    explicit = prefs.get("device_type")
    if isinstance(explicit, str) and explicit in CAPABILITY_PROMPT_MAP:
        return explicit

    profile = get_device_profile(device_id) if device_id else None
    if profile is None:
        return "esp32_xy_plotter"

    combined = f"{profile.model} {profile.profile_id}".lower()
    if any(hint in combined for hint in _WRITING_HINTS):
        return "esp32_writing_machine"
    if any(hint in combined for hint in _PLOTTER_HINTS):
        return "esp32_xy_plotter"

    features = set(profile.capability.supported_features)
    if "text" in features and "vector_path" not in features:
        return "esp32_writing_machine"
    return "esp32_xy_plotter"
