"""Preset shape facade for DLC core."""

from __future__ import annotations

from typing import Any

from xiaozhi_drawing.preset_shapes import get_preset_svg as _get_preset_svg


def get_preset(name: str, *, size: int = 180) -> dict[str, Any]:
    """Return a preset shape SVG path by name.

    Supported names: circle, square, triangle, star, heart, crescent.
    """
    return _get_preset_svg(name, size=size)
