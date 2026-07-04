"""Tests for dlc_core draw facade."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dlc_core.draw import handle_draw, handle_draw_from_image


@pytest.mark.asyncio
@patch("dlc_core.draw._try_preset_or_font")
@patch("dlc_core.draw._generate_image")
async def test_handle_draw_preset_circle(mock_generate, mock_preset) -> None:
    mock_preset.return_value = {
        "status": "success",
        "svg_path": "M0,0 L1,1",
        "preview_svg": "<svg></svg>",
        "width": 180,
        "height": 180,
        "model": "preset:circle",
        "error": None,
    }
    result = await handle_draw("画一个圆", device_id="dev-1")
    assert result["status"] == "success"
    assert result["model"] == "preset:circle"
    assert result["error"] is None
    mock_preset.assert_called_once()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
@patch("dlc_core.draw._try_preset_or_font")
@patch("dlc_core.draw._generate_image")
async def test_handle_draw_ai_disabled_in_p1(mock_generate, mock_preset) -> None:
    mock_preset.return_value = None
    result = await handle_draw("画一只猫", device_id="dev-1", allow_dashscope=False)
    assert result["status"] == "failed"
    assert "P1" in result["error"] or "disabled" in result["error"].lower()
    mock_generate.assert_not_called()


@pytest.mark.asyncio
@patch("dlc_core.draw._try_preset_or_font")
@patch("dlc_core.draw._generate_image")
async def test_handle_draw_allow_dashscope_tries_generation(mock_generate, mock_preset) -> None:
    mock_preset.return_value = None
    mock_generate.return_value = {
        "status": "success",
        "svg_path": "M0,0",
        "preview_svg": "<svg></svg>",
        "width": 180,
        "height": 180,
        "model": "dashscope",
        "error": None,
    }
    result = await handle_draw("画一只猫", device_id="dev-1", allow_dashscope=True)
    assert result["status"] == "success"
    assert result["model"] == "dashscope"
    mock_generate.assert_called_once()


@pytest.mark.asyncio
@patch("dlc_core.draw._handle_device_draw")
async def test_handle_draw_from_image_success(mock_handler) -> None:
    mock_handler.return_value = {
        "status": "success",
        "image_url": "https://example.com/img.png",
        "svg_path": "M0,0 L1,1",
        "width": 200,
        "height": 200,
        "model": "provided_image",
        "error": None,
    }
    result = await handle_draw_from_image("https://example.com/img.png", device_id="dev-1")
    assert result["status"] == "success"
    assert result["svg_path"] == "M0,0 L1,1"
    assert result["preview_svg"].startswith("<svg")
    assert result["width"] == 200
    assert result["height"] == 200
    assert result["model"] == "provided_image"
    assert result["error"] is None
    mock_handler.assert_awaited_once_with("", device_id="dev-1", image_url="https://example.com/img.png")


@pytest.mark.asyncio
@patch("dlc_core.draw._handle_device_draw")
async def test_handle_draw_from_image_failed(mock_handler) -> None:
    mock_handler.return_value = {
        "status": "failed",
        "image_url": "",
        "svg_path": None,
        "width": 0,
        "height": 0,
        "model": "LiMa 生图",
        "error": "SVG conversion failed",
    }
    result = await handle_draw_from_image("https://example.com/bad.png")
    assert result["status"] == "failed"
    assert result["svg_path"] == ""
    assert result["preview_svg"] == ""
    assert result["error"] == "SVG conversion failed"
    mock_handler.assert_awaited_once_with("", device_id=None, image_url="https://example.com/bad.png")


@pytest.mark.asyncio
@patch("dlc_core.draw._handle_device_draw")
async def test_handle_draw_from_image_invalid_url(mock_handler) -> None:
    result = await handle_draw_from_image("not-a-url")
    assert result["status"] == "failed"
    assert "image_url" in result["error"].lower()
    mock_handler.assert_not_awaited()
