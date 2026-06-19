"""Device role routing preference tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.model_routing import (
    DEVICE_ROLE_PREFERENCES,
    get_preferred_backend,
    get_route_role_alternatives,
)
from device_gateway.tasks import reset_tasks_for_tests


def setup_function():
    reset_tasks_for_tests()


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


def test_get_preferred_backend_for_control():
    result = get_preferred_backend("device_control")
    assert result is not None
    assert result["backend"] == "deterministic"


def test_get_preferred_backend_for_draw():
    result = get_preferred_backend("device_draw")
    assert result is not None
    assert result["backend"] == "dashscope_wanx"


def test_get_preferred_backend_for_write():
    result = get_preferred_backend("device_write")
    assert result is not None
    assert result["backend"] == "deterministic"


def test_get_preferred_backend_for_vector():
    result = get_preferred_backend("device_vector")
    assert result is not None
    assert result["backend"] == "opencv_contour"


def test_get_preferred_backend_for_unknown_role():
    result = get_preferred_backend("nonexistent_role")
    assert result is None


def test_get_route_role_alternatives_for_draw():
    alternatives = get_route_role_alternatives("device_draw")
    assert len(alternatives) == 2
    assert alternatives[0]["backend"] == "dashscope_wanx"
    assert alternatives[1]["backend"] == "dashscope_flux"


def test_get_route_role_alternatives_for_control():
    alternatives = get_route_role_alternatives("device_control")
    assert len(alternatives) == 1
    assert alternatives[0]["backend"] == "deterministic"


def test_get_route_role_alternatives_for_unknown():
    alternatives = get_route_role_alternatives("nonexistent_role")
    assert len(alternatives) == 0


def test_device_role_preferences_covers_all_roles():
    """All valid route roles should have preferences defined."""
    valid_roles = {"device_control", "device_write", "device_draw", "device_vector", "device_unknown"}
    for role in valid_roles:
        assert role in DEVICE_ROLE_PREFERENCES, f"Missing preferences for {role}"
        assert len(DEVICE_ROLE_PREFERENCES[role]) > 0, f"Empty preferences for {role}"
