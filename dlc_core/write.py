"""Handwriting facade for DLC core."""

from __future__ import annotations

from typing import Any

from device_gateway.device_write_handler import handle_device_write as _handle_device_write
from dlc_core.safety import MAX_TEXT_LENGTH


async def handle_write(
    text: str,
    *,
    font_style: str = "default",
    size: str = "medium",
    device_id: str | None = None,
) -> dict[str, Any]:
    """Convert text to a motion path for the drawing machine.

    Returns:
        {
            "status": "success" | "failed",
            "path_data": list[dict],
            "preview_svg": str,
            "width": int,
            "height": int,
            "model": str,
            "error": str | None,
        }
    """
    if len(text) > MAX_TEXT_LENGTH:
        return {
            "status": "failed",
            "path_data": [],
            "preview_svg": "",
            "width": 0,
            "height": 0,
            "model": "deterministic",
            "error": f"text too long: {len(text)} > {MAX_TEXT_LENGTH}",
        }
    return await _handle_device_write(text, device_id=device_id, font_style=font_style, size=size)
