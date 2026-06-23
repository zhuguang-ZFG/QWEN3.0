"""设备写字路由 - device_write 模式（确定性，无 LLM）"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from device_gateway.path_pipeline import text_to_path, preview_svg

logger = logging.getLogger(__name__)

# 字体样式映射
FONT_STYLES = {
    "default": {"scale": 1.0, "spacing": 1.0},
    "handwriting": {"scale": 0.9, "spacing": 1.2},
    "calligraphy": {"scale": 1.1, "spacing": 0.9},
}

# 字体大小映射
FONT_SIZES = {
    "small": {"scale": 0.5, "target_height": 30},
    "medium": {"scale": 1.0, "target_height": 60},
    "large": {"scale": 1.5, "target_height": 90},
}

# ── Simplification logger ───────────────────────────────────────────────────────

ARTIFACT_DIR = Path("device_artifacts")


def record_simplification(
    device_id: str,
    task_id: str,
    simplification_type: str,
    reason: str,
    original: dict[str, Any],
    constrained: dict[str, Any],
) -> None:
    """Record a profile simplification decision to artifact log.

    This must be called whenever apply_profile_constraints() makes a change
    (downgrade, cap, gate) to the task. Silent geometry repair is FORBIDDEN.
    """
    if not device_id or not task_id:
        logger.warning("Cannot record simplification: missing device_id or task_id")
        return

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "timestamp": now,
        "device_id": device_id,
        "task_id": task_id,
        "simplification_type": simplification_type,
        "reason": reason,
        "original": original,
        "constrained": constrained,
    }

    log_path = ARTIFACT_DIR / f"simplification_{device_id}.log"

    try:
        log_path.parent.mkdir(exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{json.dumps(record, ensure_ascii=False)}\n")
        logger.debug("Recorded simplification: device=%s, type=%s", device_id, simplification_type)
    except (OSError, ValueError) as e:
        logger.warning("Failed to record simplification to artifact log: %s", e)


# ── Handlers ────────────────────────────────────────────────────────────────────


def _resolve_font_params(font_style: str, size: str) -> float:
    """Compute combined scale factor from font style and size."""
    fp = FONT_STYLES.get(font_style, FONT_STYLES["default"])
    sp = FONT_SIZES.get(size, FONT_SIZES["medium"])
    return fp["scale"] * sp["scale"]


def _compute_bounds(path_list: list[dict]) -> tuple[int, int]:
    """Compute width/height from path points with margin."""
    if not path_list:
        return 100, 50
    xs = [p["x"] for p in path_list]
    ys = [p["y"] for p in path_list]
    return int(max(xs) - min(xs)) + 20, int(max(ys) - min(ys)) + 20


async def handle_device_write(
    text: str, device_id: str | None = None, font_style: str = "default", size: str = "medium"
) -> dict[str, Any]:
    """
    处理设备写字请求（确定性路径，不调用 LLM）

    Args:
        text: 要写的文字
        device_id: 设备 ID
        font_style: 字体样式 (default, handwriting, calligraphy)
        size: 字体大小 (small, medium, large)

    Returns:
        {
            'status': 'success' | 'failed',
            'path_data': list,  # 路径点列表
            'preview_svg': str,  # 预览 SVG
            'width': int,
            'height': int,
            'model': 'deterministic',
            'error': str | None
        }
    """
    logger.info(f"Device {device_id} write request: {text[:30]}... (font={font_style}, size={size})")
    try:
        scale = _resolve_font_params(font_style, size)
        path_list = text_to_path(text, origin_x=5.0, origin_y=20.0, scale=scale)
        width, height = _compute_bounds(path_list)
        return {
            "status": "success",
            "path_data": path_list,
            "preview_svg": preview_svg(path_list, width, height),
            "width": width,
            "height": height,
            "model": "deterministic",
            "error": None,
        }

    except Exception as e:
        logger.error(f"Device write failed: {e}")
        return {
            "status": "failed",
            "path_data": [],
            "preview_svg": "",
            "width": 0,
            "height": 0,
            "model": "deterministic",
            "error": str(e),
        }
