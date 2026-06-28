"""写字意图检测 + 字体转路径快速路径（从 device_draw_handler 拆出，保 ≤300 行）。

触发逻辑（两者结合）：
1. prompt 含「写：/write:」前缀 → 提取后文，走字体路径
2. 否则设备类型是 esp32_writing_machine 且 prompt 不含「画/绘/draw」关键词 → 整个 prompt 走字体路径
3. 否则返回 None（走生图）

返回结构与 _try_preset_shape（device_draw_handler.py）一致，下游 _finalize_draw_response 无需改动。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from device_gateway.draw_prompt_enhancer import resolve_device_type
from xiaozhi_drawing.text_to_path import text_to_svg_path

logger = logging.getLogger(__name__)

# 显式写字前缀：中英文冒号
_WRITE_PREFIX_RE = re.compile(r"^\s*(?:写|write|handwrite|手写)\s*[:：]\s*(.+)$", re.IGNORECASE)
# 画图关键词（命中则强制走生图，覆盖写字机默认）
_DRAW_KEYWORDS = ("画", "绘", "draw", "paint", "sketch")


def _extract_text_from_prompt(prompt: str) -> str | None:
    """匹配「写：xxx」前缀，返回要写的文字内容；不匹配返回 None。"""
    m = _WRITE_PREFIX_RE.match(prompt.strip())
    return m.group(1).strip() if m else None


def _is_draw_intent(prompt: str) -> bool:
    """检测是否为画图意图（含画图关键词）。"""
    low = prompt.lower()
    return any(kw in low for kw in _DRAW_KEYWORDS)


def try_text_to_handwriting(
    prompt: str, device_id: str | None, device_type: str | None = None
) -> dict[str, Any] | None:
    """检测写字意图：匹配则用 fonttools 转手写体路径返回；不匹配返回 None。

    返回结构与 _try_preset_shape 一致（status/image_url/svg_path/width/height/model/error）。
    """
    # 1. 显式前缀优先
    text = _extract_text_from_prompt(prompt)
    # 2. 否则按设备类型（writing_machine 默认写字，除非含画图关键词）
    if text is None:
        dtype = device_type or (resolve_device_type(device_id, {}) if device_id else None)
        if dtype == "esp32_writing_machine" and not _is_draw_intent(prompt):
            text = prompt.strip()
    if not text:
        return None

    logger.info("检测到写字意图，使用字体转路径: %s", text[:50])
    result = text_to_svg_path(text)
    if result["status"] != "success":
        # 字体缺失/渲染失败：记录但不阻断（返回 None 让链路继续走生图）
        logger.warning("字体转路径失败，回退到生图: %s", result.get("error"))
        return None

    # 转成与 _try_preset_shape 一致的结构（draw_responses builder 消费）
    motion_err = _check_motion_bounds(result["svg_path"])
    if motion_err:
        logger.warning("手写体路径越界: %s", motion_err)
        return {
            "status": "failed",
            "image_url": "",
            "svg_path": "",
            "width": result["width"],
            "height": result["height"],
            "model": "handwriting:font",
            "error": f"Motion bounds precheck failed: {motion_err}",
            "preset": False,
        }
    return {
        "status": "success",
        "image_url": "",
        "svg_path": result["svg_path"],
        "width": result["width"],
        "height": result["height"],
        "model": "handwriting:font",
        "error": None,
        "preset": False,
        "font": result.get("font"),
    }


def _check_motion_bounds(svg_path: str) -> str | None:
    """路径越界预检（复用 path_pipeline，避免循环导入延迟导入）。"""
    try:
        from device_gateway.path_pipeline import precheck_draw_motion_path

        return precheck_draw_motion_path(svg_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("motion bounds 预检失败（跳过）: %s", exc)
        return None
