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

from device_gateway.device_profile.registry import get_device_profile

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "你是 LiMa 绘图助手，专为 ESP32 笔绘机生成可执行的简笔画指令。"
    "【输出约束】只用黑色线条，纯白背景，无阴影无填充无文字，无渐变，"
    "单笔连续线描风格（coloring book outline），每条线尽量一笔画成，"
    "线条清晰连续，构图居中主体占60-80%，"
    "用最少的线条表达特征，避免密集交叉线和细碎纹理，"
    "封闭图形线条完全闭合，线条间距至少5px，图形轮廓优先内部细节从简。"
    "【失败处理】描述过于复杂时主动建议简化或分步绘制；"
    "生成前自检：这个描述能在设备能力范围内完成吗？"
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

_MAX_FAILED = 5

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


def _assemble_instruction_parts(
    device_type: str,
    conversation_context: str,
    previous_failed_prompts: list[str] | None,
) -> list[str]:
    """Build the ordered list of system/capability/retry instruction fragments."""
    parts = [SYSTEM_INSTRUCTION]
    if conversation_context:
        parts.append(f"【对话上下文】{conversation_context}")

    capability = CAPABILITY_PROMPT_MAP.get(device_type, "")
    if capability:
        parts.append(capability)

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
) -> str:
    """Wrap a user description with pen-plotter constraints.

    Args:
        user_prompt: raw user description, e.g. "画一只猫".
        style: one of 简约 / 可爱 / 写实轮廓.
        complexity: one of 低 / 中 / 高.
        device_type: device profile key in CAPABILITY_PROMPT_MAP.
        previous_failed_prompts: prior prompts that failed generation/vectorization.
        conversation_context: recent successful/failed draw turns for this device.

    Returns:
        A constrained prompt ready for the image generation backend.
    """
    user_prompt = _normalize_user_prompt(user_prompt, conversation_context)
    strokes = COMPLEXITY_STROKES.get(complexity, COMPLEXITY_STROKES["中"])
    medium_desc = f"{complexity}复杂度（{strokes}）"

    prefix = "。".join(_assemble_instruction_parts(device_type, conversation_context, previous_failed_prompts))
    return (
        f"{prefix}。"
        f"{_build_subject_expansion(user_prompt)}，"
        f"{_build_style_hint(style, medium_desc)}，"
        "纯黑白线条图，纯白背景，无文字。"
    )


def reset_draw_prompt_history_for_tests(device_id: str | None = None) -> None:
    """Clear failed prompt history and conversation turns (test isolation)."""
    try:
        from session_memory.device_draw_memory import reset_device_draw_session

        reset_device_draw_session(device_id)
    except Exception as exc:
        logger.info("draw prompt history reset skipped: %s", exc)


def get_draw_conversation_context(device_id: str | None, current_prompt: str = "") -> str:
    """Return formatted multi-turn draw context for prompt enhancement."""
    if not device_id:
        return ""
    try:
        from session_memory.device_draw_memory import format_device_draw_conversation_context

        return format_device_draw_conversation_context(
            device_id,
            exclude_prompt=(current_prompt or "").strip(),
        )
    except Exception as exc:
        logger.warning("get_draw_conversation_context failed for %s: %s", device_id, exc)
        return ""


def record_device_draw_turn(
    device_id: str | None,
    prompt: str,
    *,
    status: str,
    error: str = "",
) -> None:
    """Persist one draw conversation turn."""
    if not device_id:
        return
    cleaned = (prompt or "").strip()[:120]
    if not cleaned:
        return
    try:
        from session_memory.device_draw_memory import record_device_draw_turn as _record_turn

        _record_turn(device_id, cleaned, status=status, error=error)
    except Exception as exc:
        logger.warning("record_device_draw_turn failed for %s: %s", device_id, exc)


def record_failed_draw_prompt(device_id: str | None, prompt: str, *, error: str = "") -> None:
    """Remember a prompt that failed generation or vectorization for retry hints."""
    if not device_id:
        return
    cleaned = (prompt or "").strip()[:120]
    if not cleaned:
        return
    try:
        from session_memory.device_draw_memory import record_device_draw_failure

        record_device_draw_failure(device_id, cleaned, error=error)
    except Exception as exc:
        logger.warning("record_failed_draw_prompt persistence failed for %s: %s", device_id, exc)


def get_failed_draw_prompts(device_id: str | None) -> list[str]:
    """Return recent failed draw prompts for a device."""
    if not device_id:
        return []
    try:
        from session_memory.device_draw_memory import list_device_draw_failures

        return list_device_draw_failures(device_id, limit=_MAX_FAILED)
    except Exception as exc:
        logger.warning("get_failed_draw_prompts failed for %s: %s", device_id, exc)
        return []


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
