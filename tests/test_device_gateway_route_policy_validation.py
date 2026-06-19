"""validate_route_policy tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.path_validator import validate_route_policy
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


def test_validate_route_policy_accepts_valid_control():
    policy = {
        "route_role": "device_control",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    validated, error = validate_route_policy(policy, "home")
    assert error is None
    assert validated["route_role"] == "device_control"


def test_validate_route_policy_rejects_unknown_role():
    policy = {
        "route_role": "unknown_role",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_rejects_control_with_model():
    policy = {
        "route_role": "device_control",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy, "home")
    assert error is not None


def test_validate_route_policy_rejects_draw_without_model():
    policy = {
        "route_role": "device_draw",
        "model_required": False,
        "primary_strategy": "image_then_vector",
        "artifact_required": "vector_path",
    }
    _, error = validate_route_policy(policy, "draw_generated")
    assert error is not None


def test_validate_route_policy_rejects_draw_wrong_strategy():
    policy = {
        "route_role": "device_draw",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "vector_path",
    }
    _, error = validate_route_policy(policy, "draw_generated")
    assert error is not None


def test_validate_route_policy_rejects_unknown_not_planner():
    policy = {
        "route_role": "device_unknown",
        "model_required": True,
        "primary_strategy": "deterministic",
        "artifact_required": "none",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_rejects_invalid_artifact():
    policy = {
        "route_role": "device_write",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "invalid",
    }
    _, error = validate_route_policy(policy)
    assert error is not None


def test_validate_route_policy_accepts_valid_draw():
    policy = {
        "route_role": "device_draw",
        "model_required": True,
        "primary_strategy": "image_then_vector",
        "artifact_required": "vector_path",
    }
    validated, error = validate_route_policy(policy, "draw_generated")
    assert error is None
    assert validated["route_role"] == "device_draw"


def test_validate_route_policy_accepts_valid_vector():
    policy = {
        "route_role": "device_vector",
        "model_required": False,
        "primary_strategy": "svg_vector",
        "artifact_required": "preview_svg",
    }
    validated, error = validate_route_policy(policy, "draw_generated")
    assert error is None
    assert validated["route_role"] == "device_vector"


def test_validate_route_policy_accepts_valid_write():
    policy = {
        "route_role": "device_write",
        "model_required": False,
        "primary_strategy": "deterministic",
        "artifact_required": "preview_svg",
    }
    validated, error = validate_route_policy(policy, "write_text")
    assert error is None
    assert validated["route_role"] == "device_write"


def test_validate_route_policy_rejects_non_dict():
    _, error = validate_route_policy("not a dict")
    assert error is not None
