"""hello frame builds a complete profile and registers by device_id."""

from __future__ import annotations

from device_gateway.device_profile import get_device_profile, profile_from_hello_frame, register_device_profile
from device_gateway.device_profile.registry import reset_device_profiles_for_tests
from device_gateway.path_workspace import resolve_workspace_mm
from device_gateway.profiles import resolve_profile, reset_profiles_for_tests


def setup_function():
    reset_device_profiles_for_tests()
    reset_profiles_for_tests()


def test_profile_from_hello_is_complete_with_product_workspace():
    profile = profile_from_hello_frame(
        "u8-1",
        {"fw_rev": "v1.0", "capabilities": ["run_path", "write_text"]},
    )
    assert profile.profile_id.startswith("hello-")
    assert profile.workspace_mm["x"] == 300.0
    from device_gateway.path_workspace import is_complete_profile as path_complete

    assert path_complete(profile)


def test_hello_register_makes_resolve_workspace_use_device_canvas():
    profile = profile_from_hello_frame(
        "u8-small",
        {"workspace_mm": {"x": 120.0, "y": 100.0, "z": 40.0}, "profile_id": "custom-u8"},
    )
    register_device_profile(profile)
    resolved = resolve_profile(device_id="u8-small")
    assert resolved.complete is True
    assert resolved.profile.workspace_mm["x"] == 120.0
    ws = resolve_workspace_mm(device_id="u8-small")
    assert ws["x"] == 120.0
    assert get_device_profile("u8-small") is not None
