"""Prompt enhancer for pen-plotter drawing generation.

Translates free-form user descriptions into a constrained prompt tuned for
Wanx / image-to-SVG / pen-plotter execution:
- black lines only, pure white background
- minimal line count, closed contours
- vectorization-friendly spacing and stroke width
"""

from __future__ import annotations


SYSTEM_INSTRUCTION = (
    "笔绘机简笔画：只用黑色线条，纯白背景，无阴影无填充无文字，"
    "线条清晰连续粗细约2-3px，构图居中主体占60-80%，"
    "用最少的线条表达特征，避免密集交叉线和细碎纹理，"
    "封闭图形线条完全闭合，线条间距至少5px，图形轮廓优先内部细节从简"
)


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
) -> str:
    """Wrap a user description with pen-plotter constraints.

    Args:
        user_prompt: raw user description, e.g. "画一只猫".
        style: one of 简约 / 可爱 / 写实轮廓.
        complexity: one of 低 / 中 / 高.

    Returns:
        A constrained prompt ready for the image generation backend.
    """
    if not isinstance(user_prompt, str):
        user_prompt = str(user_prompt)
    user_prompt = user_prompt.strip()
    if not user_prompt:
        user_prompt = "一个简单图形"

    strokes = COMPLEXITY_STROKES.get(complexity, COMPLEXITY_STROKES["中"])

    return (
        f"{SYSTEM_INSTRUCTION}。"
        f"画一个{user_prompt}的简笔画，"
        f"{style}风格，{complexity}复杂度（{strokes}），"
        "纯黑白线条图，纯白背景，无文字。"
    )
