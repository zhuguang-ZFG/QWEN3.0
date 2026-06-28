"""Task creation must route natural-language draw prompts through device_draw_handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from device_gateway.tasks import project_to_motion_task_async, reset_tasks_for_tests


@pytest.fixture(autouse=True)
def _reset_store():
    reset_tasks_for_tests()
    yield
    reset_tasks_for_tests()


@pytest.mark.asyncio
async def test_draw_generated_natural_language_uses_device_draw_handler():
    voice_task = {
        "capability": "draw_generated",
        "params": {"prompt": "画一只猫"},
        "source": "voice",
    }
    mock_draw = AsyncMock(
        return_value={
            "status": "success",
            "image_url": "http://example.com/cat.jpg",
            "svg_path": "M 10 10 L 50 50 L 90 10 Z",
            "width": 180,
            "height": 180,
            "model": "wanx2.1-t2i-turbo",
            "error": None,
        }
    )
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = await project_to_motion_task_async("dev-draw-1", voice_task)

    assert "error" not in task
    mock_draw.assert_awaited_once_with(
        "画一只猫", device_id="dev-draw-1", user_preferences={}, image_url=None
    )
    params = task["params"]
    assert params["source_capability"] == "draw_generated"
    assert params["prompt"] == "画一只猫"
    assert len(params["path"]) > 2
    assert "preview_svg" in params


@pytest.mark.asyncio
async def test_draw_generated_svg_prompt_skips_device_draw_handler():
    voice_task = {
        "capability": "draw_generated",
        "params": {"prompt": "M 0 0 L 10 0 L 10 10 Z"},
        "source": "api",
    }
    mock_draw = AsyncMock()
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = await project_to_motion_task_async("dev-draw-2", voice_task)

    assert "error" not in task
    mock_draw.assert_not_called()
    assert len(task["params"]["path"]) >= 3


@pytest.mark.asyncio
async def test_draw_generated_handler_failure_becomes_failed_task():
    voice_task = {
        "capability": "draw_generated",
        "params": {"prompt": "画一只猫"},
        "source": "voice",
    }
    mock_draw = AsyncMock(
        return_value={
            "status": "failed",
            "image_url": "",
            "svg_path": None,
            "width": 0,
            "height": 0,
            "model": "wanx2.1-t2i-turbo",
            "error": "quota exceeded",
        }
    )
    with patch("device_gateway.task_draw_params.handle_device_draw", mock_draw):
        task = await project_to_motion_task_async("dev-draw-3", voice_task)

    assert task.get("error", {}).get("code") == "draw_failed"
    assert "quota exceeded" in str(task.get("error", {}).get("reason", ""))
