"""SSRF hardening tests for device_gateway.device_draw_handler.

Code review HIGH: device_draw_handler previously accepted any caller-provided
image URL (http(s) + <2000 chars) and passed it straight to SVG conversion,
bypassing the SEC-04 host allowlist. These tests pin the fix:
- provided image_url must pass device_gateway.image_url_validation first
- generated image URLs from the internal DashScope backend skip host allowlist
  but still rely on pin-IP (private/loopback blocking), via allowed_hosts=frozenset()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import device_gateway.device_draw_handler as draw_handler


@pytest.mark.asyncio
async def test_provided_image_url_rejected_when_not_allowlisted() -> None:
    with (
        patch.object(
            draw_handler,
            "validate_image_url_async",
            new=AsyncMock(return_value=(None, "image_url host not allowed: evil.com")),
        ) as validate_mock,
        patch.object(
            draw_handler,
            "_convert_and_optimize",
            new=AsyncMock(),
        ) as convert_mock,
    ):
        response = await draw_handler._convert_provided_image(
            "https://evil.com/img.png",
            {"model": "test-model"},
            "dev-1",
            "draw a cat",
        )
        validate_mock.assert_awaited_once_with("https://evil.com/img.png")
        convert_mock.assert_not_awaited()
        assert response["status"] == "failed"
        assert "not allowed" in response.get("error", "").lower()


@pytest.mark.asyncio
async def test_provided_image_url_converted_when_allowlisted() -> None:
    with (
        patch.object(
            draw_handler,
            "validate_image_url_async",
            new=AsyncMock(return_value=("https://api.telegram.org/file/bot123/img.png", None)),
        ) as validate_mock,
        patch.object(
            draw_handler,
            "_convert_and_optimize",
            new=AsyncMock(return_value={"status": "success"}),
        ) as convert_mock,
    ):
        response = await draw_handler._convert_provided_image(
            "https://api.telegram.org/file/bot123/img.png",
            {"model": "test-model"},
            "dev-1",
            "draw a cat",
        )
        validate_mock.assert_awaited_once()
        convert_mock.assert_awaited_once()
        _, kwargs = convert_mock.call_args
        assert kwargs.get("allowed_hosts") == frozenset()
        assert response["status"] == "success"


@pytest.mark.asyncio
async def test_generated_image_url_skips_host_allowlist() -> None:
    """URLs returned by DashScope are trusted; fetch_pinned still blocks private IPs."""
    with (
        patch.object(
            draw_handler,
            "_generate_image",
            new=AsyncMock(
                return_value={"status": "success", "images": [{"url": "https://dashscope.example.com/out.png"}]}
            ),
        ),
        patch.object(
            draw_handler,
            "_convert_and_optimize",
            new=AsyncMock(return_value={"status": "success"}),
        ) as convert_mock,
        patch.object(
            draw_handler,
            "_try_fast_paths",
            return_value=None,
        ),
        patch.object(
            draw_handler,
            "screen_drawing_request",
            return_value={"simplified_prompt": "cat", "feasible": True},
        ),
    ):
        response = await draw_handler._try_preset_or_generate(
            "cat",
            "dev-1",
            {
                "model": "test",
                "size": "512x512",
                "device_type": "esp32_xy_plotter",
                "style": "简约",
                "complexity": "中",
            },
            None,
        )
        convert_mock.assert_awaited_once()
        _, kwargs = convert_mock.call_args
        assert kwargs.get("allowed_hosts") == frozenset()
        assert response["status"] == "success"
