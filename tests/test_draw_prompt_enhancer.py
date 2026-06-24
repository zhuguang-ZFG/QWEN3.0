"""Tests for plotter-focused prompt enhancement."""

from __future__ import annotations

import pytest

from device_gateway.device_profile.models import DeviceCapability, DeviceProfile
from device_gateway.device_profile.registry import (
    get_device_profile,
    register_device_profile,
    reset_device_profiles_for_tests,
)
from device_gateway.draw_prompt_enhancer import (
    classify_plotter_complexity,
    enhance_drawing_prompt,
    screen_drawing_request,
    simplify_prompt_for_plotter,
)


@pytest.fixture(autouse=True)
def _reset_profiles():
    reset_device_profiles_for_tests()
    yield
    reset_device_profiles_for_tests()


class TestClassifyPlotterComplexity:
    def test_simple_prompt(self):
        assert classify_plotter_complexity("画一个圆") == "simple"
        assert classify_plotter_complexity("apple") == "simple"

    def test_medium_prompt(self):
        assert classify_plotter_complexity("画一棵树") == "medium"
        assert classify_plotter_complexity("画一个卡通机器人") == "medium"

    def test_complex_prompt(self):
        assert classify_plotter_complexity("画一座城市和人群的照片") == "complex"
        assert classify_plotter_complexity("a photorealistic cat with fur and shadow") == "complex"


class TestSimplifyPrompt:
    def test_strip_complex_modifiers(self):
        simplified = simplify_prompt_for_plotter("画一只毛茸茸的猫在阳光下")
        assert "毛茸茸" not in simplified
        assert "阳光下" not in simplified
        assert "简笔画" in simplified

    def test_take_first_subject(self):
        assert "苹果" in simplify_prompt_for_plotter("画一个苹果和一座房子")
        assert "房子" not in simplify_prompt_for_plotter("画一个苹果和一座房子")

    def test_fallback_for_empty(self):
        result = simplify_prompt_for_plotter("   ")
        assert "简笔画" in result


class TestScreenDrawingRequest:
    def test_feasible_when_no_profile(self):
        result = screen_drawing_request("画一个圆", "unknown-device")
        assert result["feasible"] is True
        assert result["complexity"] == "simple"

    def test_rejected_for_complex_on_limited_device(self):
        profile = DeviceProfile(
            device_id="dev-small",
            max_path_points=50,
            workspace_mm={"x": 60, "y": 60, "z": 10},
            capabilities=("run_path",),
            capability=DeviceCapability(supported_features=("vector_path",)),
        )
        register_device_profile(profile)
        result = screen_drawing_request("画一座城市风景", "dev-small")
        assert result["feasible"] is False
        assert result["complexity"] == "complex"
        assert result["max_allowed"] == "simple"
        assert "建议简化" in result["suggestion"]

    def test_medium_allowed_on_capable_device(self):
        profile = DeviceProfile(
            device_id="dev-medium",
            max_path_points=120,
            workspace_mm={"x": 100, "y": 100, "z": 10},
            capabilities=("run_path",),
            capability=DeviceCapability(supported_features=("vector_path",)),
        )
        register_device_profile(profile)
        result = screen_drawing_request("画一棵树", "dev-medium")
        assert result["feasible"] is True
        assert result["complexity"] == "medium"


class TestEnhancedPromptContent:
    def test_includes_constraints_and_examples(self):
        prompt = enhance_drawing_prompt("画一只猫")
        assert "绝对禁止" in prompt
        assert "正面示例" in prompt
        assert "设备约束" in prompt

    def test_includes_device_profile_constraints(self):
        profile = DeviceProfile(
            device_id="dev-constraint",
            max_path_points=80,
            workspace_mm={"x": 80, "y": 80, "z": 10},
            capabilities=("run_path",),
            capability=DeviceCapability(supported_features=("vector_path",)),
        )
        register_device_profile(profile)
        prompt = enhance_drawing_prompt("画一只猫", device_profile=get_device_profile("dev-constraint"))
        assert "80x80mm" in prompt
        assert "80" in prompt
