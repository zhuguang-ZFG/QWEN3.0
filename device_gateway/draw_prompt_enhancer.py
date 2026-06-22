"""Prompt enhancer for pen-plotter drawing generation.

Translates free-form user descriptions into a constrained prompt tuned for
Wanx / image-to-SVG / pen-plotter execution:
- black lines only, pure white background
- minimal line count, single-stroke / closed-contour hints for vectorization
- vectorization-friendly spacing (no fixed px stroke width)
"""

from __future__ import annotations


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
        "设备能力：XY平台单笔画绘制，支持G-code，不支持颜色填充。"
        "线条粗细固定，请在设计中注意线条密度避免卡笔。"
    ),
    "esp32_writing_machine": (
        "设备能力：中文汉字书写，支持多种字体，可连续书写多行。"
        "注意汉字笔画顺序和连笔处理。"
    ),
}

COMPLEXITY_STROKES = {
    "低": "约10笔画",
    "中": "约20笔画",
    "高": "约40笔画",
}


def enhance_drawing_prompt(
    user_prompt: str,
    *,
    style: str = "简约",
    complexity: str = "中",
    device_type: str = "esp32_xy_plotter",
    previous_failed_prompts: list[str] | None = None,
) -> str:
    """Wrap a user description with pen-plotter constraints.

    Args:
        user_prompt: raw user description, e.g. "画一只猫".
        style: one of 简约 / 可爱 / 写实轮廓.
        complexity: one of 低 / 中 / 高.
        device_type: device profile key in CAPABILITY_PROMPT_MAP.
        previous_failed_prompts: prior prompts that failed generation/vectorization.

    Returns:
        A constrained prompt ready for the image generation backend.
    """
    if not isinstance(user_prompt, str):
        user_prompt = str(user_prompt)
    user_prompt = user_prompt.strip()
    if not user_prompt:
        user_prompt = "一个简单图形"

    strokes = COMPLEXITY_STROKES.get(complexity, COMPLEXITY_STROKES["中"])
    capability = CAPABILITY_PROMPT_MAP.get(device_type, "")

    retry_hint = ""
    if previous_failed_prompts:
        retry_hint = f"注意：之前以下描述生成失败，请调整：{previous_failed_prompts[-1]}"

    parts = [SYSTEM_INSTRUCTION]
    if capability:
        parts.append(capability)
    if retry_hint:
        parts.append(retry_hint)

    prefix = "。".join(parts)
    return (
        f"{prefix}。"
        f"画一个{user_prompt}的简笔画，"
        f"{style}风格，{complexity}复杂度（{strokes}），"
        "纯黑白线条图，纯白背景，无文字。"
    )
