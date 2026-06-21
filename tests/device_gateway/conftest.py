"""Shared fixtures for device_gateway route tests."""

from unittest.mock import AsyncMock

import pytest

from routes.device_gateway_helpers import _reset_for_tests


@pytest.fixture(autouse=True)
def _device_gateway_test_env(monkeypatch):
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=test-device-token")
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
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
    _reset_for_tests()
    yield
    _reset_for_tests()
