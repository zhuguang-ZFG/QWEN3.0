"""Tests for try_backends wiring in device_draw _generate_image."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from device_gateway.device_draw_handler import _generate_image


@pytest.mark.asyncio
async def test_fallback_off_single_attempt(monkeypatch):
    """LIMA_AUTO_FALLBACK=0: first backend fails → only 1 attempt, returns failed."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "0")

    call_count = 0

    def _gen(**kwargs):
        nonlocal call_count
        call_count += 1
        return {"status": "failed", "images": [], "task_id": "", "error": "mock failure"}

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.generate = _gen

    with patch(
        "device_gateway.device_draw_handler.DashScopeImageClient",
        mock_client_cls,
    ):
        result = await _generate_image(
            "test prompt",
            model="",
            size="512*512",
            device_id="test-fallback-off",
        )

    assert result["status"] == "failed"
    assert call_count == 1, "fallback disabled: must only try 1 backend"


@pytest.mark.asyncio
async def test_fallback_on_first_fails_second_succeeds(monkeypatch):
    """LIMA_AUTO_FALLBACK=1: first fails, second succeeds → returns success."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    call_count = 0

    def _gen(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"status": "failed", "images": [], "task_id": "", "error": "wanx down"}
        return {
            "status": "success",
            "images": [{"url": "http://example.com/img.jpg"}],
            "task_id": "t1",
            "error": None,
        }

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.generate = _gen

    with patch(
        "device_gateway.device_draw_handler.DashScopeImageClient",
        mock_client_cls,
    ):
        result = await _generate_image(
            "fallback test",
            model="",
            size="512*512",
            device_id="test-fallback-on",
        )

    assert result["status"] == "success"
    assert call_count == 2, "fallback on: must try both backends"
    assert result["images"][0]["url"] == "http://example.com/img.jpg"


@pytest.mark.asyncio
async def test_fallback_on_all_fail_returns_failed_contract(monkeypatch):
    """LIMA_AUTO_FALLBACK=1: all backends fail → returns failed dict (no uncaught exception)."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    def _gen(**kwargs):
        return {"status": "failed", "images": [], "task_id": "", "error": "always fail"}

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.generate = _gen

    with patch(
        "device_gateway.device_draw_handler.DashScopeImageClient",
        mock_client_cls,
    ):
        # Must NOT raise — contract is failed dict.
        result = await _generate_image(
            "all fail test",
            model="",
            size="512*512",
            device_id="test-all-fail",
        )

    assert result["status"] == "failed"
    assert "error" in result


@pytest.mark.asyncio
async def test_timeout_triggers_fallback(monkeypatch):
    """LIMA_AUTO_FALLBACK=1: first backend times out → falls back to second."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    mock_call = AsyncMock(
        side_effect=[
            asyncio.TimeoutError("simulated per-backend timeout"),
            {
                "status": "success",
                "images": [{"url": "http://example.com/img2.jpg"}],
                "task_id": "t2",
                "error": None,
            },
        ]
    )

    with patch(
        "device_gateway.device_draw_handler._call_dashscope_generate",
        mock_call,
    ):
        result = await _generate_image(
            "timeout test",
            model="",
            size="512*512",
            device_id="test-timeout",
        )

    assert result["status"] == "success"
    assert mock_call.call_count == 2, "timeout on first should trigger fallback to second"


@pytest.mark.asyncio
async def test_config_model_overrides_only_primary_backend(monkeypatch):
    """Caller model overrides wanx only; flux fallback keeps mapping model."""
    monkeypatch.setenv("LIMA_AUTO_FALLBACK", "1")

    captured_models: list[str] = []

    def _gen(**kwargs):
        captured_models.append(kwargs.get("model", ""))
        if len(captured_models) == 1:
            return {"status": "failed", "images": [], "task_id": "", "error": "wanx down"}
        return {
            "status": "success",
            "images": [{"url": "http://example.com/img3.jpg"}],
            "task_id": "t3",
            "error": None,
        }

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.generate = _gen

    with patch(
        "device_gateway.device_draw_handler.DashScopeImageClient",
        mock_client_cls,
    ):
        result = await _generate_image(
            "model override test",
            model="custom-model-v2",
            size="512*512",
            device_id="test-model-override",
        )

    assert result["status"] == "success"
    assert captured_models == ["custom-model-v2", "flux-schnell"]
