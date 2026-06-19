"""Sticky route memory tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.device_route_memory import (
    get_route_memory,
    record_route_decision,
    reset_route_memory_for_tests,
)
from device_gateway.profiles import reset_profiles_for_tests


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


@pytest.fixture(autouse=True)
def _mock_device_draw(monkeypatch):
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


def test_record_route_decision_and_get_memory():
    record_route_decision("device-1", "backend-a", True)
    memory = get_route_memory("device-1")

    assert memory["device_id"] == "device-1"
    assert memory["preferred_backends"] == ["backend-a"]
    assert memory["success_count"] == 1
    assert memory["total_count"] == 1


def test_multiple_route_decisions_update_memory():
    record_route_decision("device-2", "backend-a", True)
    record_route_decision("device-2", "backend-b", False)
    record_route_decision("device-2", "backend-a", True)

    memory = get_route_memory("device-2")

    assert "backend-a" in memory["preferred_backends"]
    assert "backend-b" in memory["preferred_backends"]
    assert memory["success_count"] == 2
    assert memory["total_count"] == 3


def test_empty_device_memory_returns_empty_dict():
    memory = get_route_memory("device-nonexistent")
    assert memory == {}
