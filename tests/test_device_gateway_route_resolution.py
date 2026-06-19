"""Device route resolution tests."""

from unittest.mock import AsyncMock

import pytest

from device_gateway.model_routing import resolve_device_route_policy
from device_gateway.tasks import create_task_from_transcript, reset_tasks_for_tests


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


def test_control_command_uses_no_model_route():
    task = create_task_from_transcript("dev-1", "home")

    assert task["route_policy"]["route_role"] == "device_control"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["primary_strategy"] == "deterministic"


def test_write_text_uses_device_write_route():
    task = create_task_from_transcript("dev-1", "write LiMa")

    assert task["route_policy"]["route_role"] == "device_write"
    assert task["route_policy"]["model_required"] is False
    assert task["route_policy"]["artifact_required"] == "preview_svg"


def test_generated_drawing_uses_device_draw_route():
    task = create_task_from_transcript("dev-1", "draw cat")

    assert task["route_policy"]["route_role"] == "device_draw"
    assert task["route_policy"]["model_required"] is True
    assert task["route_policy"]["artifact_required"] == "vector_path"


def test_svg_like_generated_drawing_uses_vector_route_without_model():
    policy = resolve_device_route_policy({"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}})

    assert policy["route_role"] == "device_vector"
    assert policy["model_required"] is False


def test_route_policy_matrix_for_hot_device_families():
    cases = [
        (
            {"capability": "home", "params": {}},
            {
                "route_role": "device_control",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "none",
                "backend": "deterministic",
            },
        ),
        (
            {"capability": "write_text", "params": {"text": "你好"}},
            {
                "route_role": "device_write",
                "model_required": False,
                "primary_strategy": "deterministic",
                "artifact_required": "preview_svg",
                "backend": "deterministic",
            },
        ),
        (
            {"capability": "draw_generated", "params": {"prompt": "画一只猫"}},
            {
                "route_role": "device_draw",
                "model_required": True,
                "primary_strategy": "image_then_vector",
                "artifact_required": "vector_path",
                "backend": "dashscope_wanx",
            },
        ),
        (
            {"capability": "draw_generated", "params": {"prompt": "M 0 0 L 10 10"}},
            {
                "route_role": "device_vector",
                "model_required": False,
                "primary_strategy": "svg_vector",
                "artifact_required": "preview_svg",
                "backend": "opencv_contour",
            },
        ),
    ]

    for voice_task, expected in cases:
        assert resolve_device_route_policy(voice_task) == expected
