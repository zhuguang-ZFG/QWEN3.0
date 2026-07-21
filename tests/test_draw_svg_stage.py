"""draw_svg_stage targets follow device workspace (0.9 margin)."""

from __future__ import annotations

from device_gateway.device_profile import profile_from_hello_frame, register_device_profile
from device_gateway.device_profile.registry import reset_device_profiles_for_tests
from device_gateway.draw_svg_stage import workspace_target_px
from device_gateway.profiles import reset_profiles_for_tests


def setup_function():
    reset_device_profiles_for_tests()
    reset_profiles_for_tests()


def test_default_target_is_90_percent_of_product_canvas():
    w, h = workspace_target_px(None)
    assert w == 270.0
    assert h == 270.0


def test_hello_small_canvas_shrinks_svg_target():
    register_device_profile(
        profile_from_hello_frame(
            "tiny",
            {"workspace_mm": {"x": 100.0, "y": 80.0, "z": 20.0}, "profile_id": "tiny-1"},
        )
    )
    w, h = workspace_target_px("tiny")
    assert w == 90.0
    assert h == 72.0
