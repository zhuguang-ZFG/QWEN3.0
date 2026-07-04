"""Drawing facade for DLC core."""

from __future__ import annotations

import asyncio
from typing import Any

from device_gateway.device_draw_handler import handle_device_draw as _handle_device_draw
from device_gateway.handwriting_path import try_text_to_handwriting

from dlc_core.presets import get_preset

PRESET_KEYWORDS = {
    "circle": ["圆", "圆形", "circle"],
    "square": ["方", "方形", "正方形", "square"],
    "triangle": ["三角", "三角形", "triangle"],
    "star": ["星", "星星", "五角星", "star"],
    "heart": ["心", "心形", "heart", "爱心"],
    "crescent": ["月", "月亮", "月牙", "crescent"],
}


def _detect_preset(prompt: str) -> str | None:
    lowered = prompt.lower()
    for shape, keywords in PRESET_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return shape
    return None


def _build_preview_svg(svg_path: str, width: int, height: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><path d="{svg_path}" fill="none" stroke="black"/></svg>'


async def _try_preset_or_font(prompt: str, device_id: str | None = None) -> dict[str, Any] | None:
    """Try preset shape or handwriting font path; return first match or None."""
    shape = _detect_preset(prompt)
    if shape:
        result = get_preset(shape, size=180)
        if result.get("status") == "success":
            return {
                "status": "success",
                "svg_path": result["svg_path"],
                "preview_svg": _build_preview_svg(result["svg_path"], result["width"], result["height"]),
                "width": result["width"],
                "height": result["height"],
                "model": f"preset:{shape}",
                "error": None,
            }

    font_result = try_text_to_handwriting(prompt, device_id=device_id, device_type="esp32_xy_plotter")
    if font_result and font_result.get("status") == "success":
        return font_result
    return None


async def _generate_image(prompt: str, device_id: str | None = None) -> dict[str, Any]:
    """P1 placeholder: full AI image generation via DashScope/fallback.

    This is intentionally minimal. Real backend convergence is tracked in
    docs/xiaozhi-cloud/08-open-questions.md Q-02.
    """
    # Defer to the existing handler when explicitly enabled.
    return await _handle_device_draw(prompt, device_id=device_id)


async def handle_draw(
    prompt: str,
    *,
    device_id: str | None = None,
    allow_dashscope: bool = False,
) -> dict[str, Any]:
    """Handle a drawing request.

    P1 strategy:
      1. Preset shape matching.
      2. Handwriting font fallback.
      3. AI generation only if allow_dashscope=True (disabled for MCP/firmware).

    Returns:
        {
            "status": "success" | "failed",
            "svg_path": str,
            "preview_svg": str,
            "width": int,
            "height": int,
            "model": str,
            "error": str | None,
        }
    """
    fast = await _try_preset_or_font(prompt, device_id=device_id)
    if fast and fast.get("status") == "success":
        return fast

    if not allow_dashscope:
        return {
            "status": "failed",
            "svg_path": "",
            "preview_svg": "",
            "width": 0,
            "height": 0,
            "model": "disabled",
            "error": "AI generation disabled in P1 for this caller (see Q-02)",
        }

    return await _generate_image(prompt, device_id=device_id)


def _failed_result(error: str, *, status: str = "failed") -> dict[str, Any]:
    """Build a standard failure/timeout result dict."""
    return {
        "status": status,
        "svg_path": "",
        "preview_svg": "",
        "width": 0,
        "height": 0,
        "model": "disabled",
        "error": error,
    }


def _image_result_from_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert raw _handle_device_draw output to the standard result shape."""
    status = raw.get("status")
    svg_path = raw.get("svg_path") or ""
    width = raw.get("width") or 0
    height = raw.get("height") or 0
    preview_svg = _build_preview_svg(svg_path, width, height) if status == "success" and svg_path else ""
    error = raw.get("error") or ("image conversion failed" if status != "success" else None)
    return {
        "status": "success" if status == "success" else "failed",
        "svg_path": svg_path,
        "preview_svg": preview_svg,
        "width": width,
        "height": height,
        "model": raw.get("model") or "provided_image",
        "error": error,
    }


async def handle_draw_from_image(
    image_url: str,
    *,
    device_id: str | None = None,
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Convert a caller-provided image URL into a drawing path.

    Includes a 25s timeout (T1) to stay within MCP tool_call_timeout (30s).
    Returns the same field shape as :func:`handle_draw`.
    """
    if not image_url or not image_url.startswith(("https://", "http://")):
        return _failed_result("image_url is required and must be an http(s) URL")

    try:
        raw = await asyncio.wait_for(
            _handle_device_draw("", device_id=device_id, image_url=image_url),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return _failed_result("image vectorization timed out", status="timeout")
    return _image_result_from_raw(raw)
