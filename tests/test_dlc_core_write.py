"""Tests for dlc_core write facade."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dlc_core.write import handle_write


@pytest.mark.asyncio
@patch("dlc_core.write._handle_device_write")
async def test_handle_write_success(mock_write) -> None:
    mock_write.return_value = {
        "status": "success",
        "path_data": [{"x": 0, "y": 0}, {"x": 10, "y": 10}],
        "preview_svg": "<svg></svg>",
        "width": 100,
        "height": 50,
        "model": "deterministic",
        "error": None,
    }
    result = await handle_write("你好", device_id="dev-1", font_style="default", size="medium")
    assert result["status"] == "success"
    assert result["path_data"]
    assert result["preview_svg"]
    assert result["width"] == 100
    assert result["height"] == 50
    assert result["error"] is None
    mock_write.assert_called_once_with("你好", device_id="dev-1", font_style="default", size="medium")


@pytest.mark.asyncio
@patch("dlc_core.write._handle_device_write")
async def test_handle_write_failure(mock_write) -> None:
    mock_write.return_value = {
        "status": "failed",
        "path_data": [],
        "preview_svg": "",
        "width": 0,
        "height": 0,
        "model": "deterministic",
        "error": "font not found",
    }
    result = await handle_write("hello")
    assert result["status"] == "failed"
    assert result["error"] == "font not found"
