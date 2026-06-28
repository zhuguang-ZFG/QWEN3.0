"""Tests for handwriting local fallback path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from device_gateway import path_pipeline
from device_gateway.task_draw_params import build_handwriting_params
from integrations.autohanding.client import AutohandingClientError, AutohandingRateLimitError


@pytest.mark.asyncio
async def test_build_handwriting_params_ascii_fallback():
    with patch("integrations.autohanding.client.convert_text", AsyncMock(side_effect=AutohandingClientError("boom"))):
        params, error = await build_handwriting_params({"text": "hello"}, "device-1")

    assert error is None
    assert params["source_capability"] == "handwriting"
    assert params["backend"] == "lima-local"
    assert params["path"]
    assert params["preview_svg"]


@pytest.mark.asyncio
async def test_build_handwriting_params_chinese_no_fallback():
    with patch("integrations.autohanding.client.convert_text", AsyncMock(side_effect=AutohandingClientError("boom"))):
        params, error = await build_handwriting_params({"text": "你好"}, "device-1")

    assert params == {}
    assert error is not None
    assert "autohanding error" in error


@pytest.mark.asyncio
async def test_build_handwriting_params_rate_limit_not_fallback():
    with patch(
        "integrations.autohanding.client.convert_text",
        AsyncMock(side_effect=AutohandingRateLimitError("limit")),
    ):
        params, error = await build_handwriting_params({"text": "hello"}, "device-1")

    assert params == {}
    assert "rate limit" in error


def test_text_to_svg_path_returns_valid_d():
    result = path_pipeline.text_to_svg_path("Hi")

    assert result["status"] == "success"
    assert result["backend"] == "lima-local"
    assert result["svg_path"].startswith("M")
    assert result["width"] > 0
    assert result["height"] > 0
    assert result["point_count"] > 0
    assert "<svg" in result["preview_svg"]


def test_motion_path_to_svg_d_pen_up_moves():
    path = [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},  # pen-up duplicate
        {"x": 5, "y": 5, "z": 0},
    ]
    d = path_pipeline._motion_path_to_svg_d(path)
    assert d.count("M") == 2
    assert d.count("L") == 1
