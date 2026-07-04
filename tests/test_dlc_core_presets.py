"""Tests for dlc_core preset shape facade."""

from __future__ import annotations

from unittest.mock import patch

from dlc_core.presets import get_preset


@patch("dlc_core.presets._get_preset_svg")
def test_get_preset_circle_returns_svg(mock_get_svg) -> None:
    mock_get_svg.return_value = {
        "status": "success",
        "svg_path": "M0,0 L1,1",
        "width": 180,
        "height": 180,
    }
    result = get_preset("circle", size=180)
    assert result["status"] == "success"
    assert result["svg_path"] == "M0,0 L1,1"
    assert result["width"] == 180
    assert result["height"] == 180
    mock_get_svg.assert_called_once_with("circle", size=180)


@patch("dlc_core.presets._get_preset_svg")
def test_get_preset_failure_propagates(mock_get_svg) -> None:
    mock_get_svg.return_value = {"status": "failed", "error": "unknown shape"}
    result = get_preset("hexagon", size=180)
    assert result["status"] == "failed"
    assert "error" in result
