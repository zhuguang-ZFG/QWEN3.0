"""Shared fixtures for device gateway profile tests."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def _mock_device_draw(monkeypatch):
    """Mock draw handler so profile tests do not call real image backends."""
    monkeypatch.setattr(
        "device_gateway.task_draw_params.handle_device_draw",
        AsyncMock(
            return_value={
                "status": "success",
                "image_url": "",
                "svg_path": "M 10 10 L 50 50 L 90 10 Z",
                "width": 180,
                "height": 180,
                "model": "test-draw",
                "error": None,
            }
        ),
    )
