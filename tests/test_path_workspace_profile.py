"""Workspace resolution prefers complete profiles and product canvas."""

from __future__ import annotations

from device_gateway.device_profile import DeviceProfile, register_device_profile
from device_gateway.device_profile.registry import reset_device_profiles_for_tests
from device_gateway.path_workspace import resolve_workspace_mm
from device_gateway.profiles import PRODUCT_WRITING_WORKSPACE_MM, register_profile, reset_profiles_for_tests
from device_gateway.safety import DEFAULT_WORKSPACE_MM


def setup_function():
    reset_profiles_for_tests()
    reset_device_profiles_for_tests()


def test_default_without_device_is_product_canvas():
    ws = resolve_workspace_mm()
    assert ws["x"] == DEFAULT_WORKSPACE_MM["x"] == 300.0
    assert ws["y"] == 300.0
    assert ws["z"] == 80.0


def test_unknown_device_id_uses_product_canvas():
    ws = resolve_workspace_mm(device_id="unknown-esp32")
    assert ws["x"] == PRODUCT_WRITING_WORKSPACE_MM["x"]
    assert ws["y"] == PRODUCT_WRITING_WORKSPACE_MM["y"]


def test_known_profile_by_device_id_wins():
    """KNOWN_PROFILES entry with matching device_id is complete for path gen."""
    register_profile(
        DeviceProfile(
            device_id="dev-a",
            profile_id="custom-200",
            model="test",
            workspace_mm={"x": 200.0, "y": 150.0, "z": 40.0},
            max_feed=1000.0,
            max_path_points=100,
            capabilities=("run_path",),
            supported_fw_prefixes=("",),
        )
    )
    ws = resolve_workspace_mm(device_id="dev-a")
    assert ws["x"] == 200.0
    assert ws["y"] == 150.0


def test_runtime_registry_profile_by_device_id_wins():
    register_device_profile(
        DeviceProfile(
            device_id="runtime-dev",
            profile_id="runtime-180",
            model="test",
            workspace_mm={"x": 180.0, "y": 120.0, "z": 30.0},
            max_feed=1000.0,
            max_path_points=100,
            capabilities=("run_path",),
            supported_fw_prefixes=("",),
        )
    )
    ws = resolve_workspace_mm(device_id="runtime-dev")
    assert ws == {"x": 180.0, "y": 120.0, "z": 30.0}


def test_bare_registry_profile_stays_incomplete_uses_product_canvas():
    """Empty profile_id must not open routing gates or claim a custom canvas."""
    from device_gateway.profiles import resolve_profile

    register_device_profile(DeviceProfile(device_id="hello-bare", profile_id="", model=""))
    resolved = resolve_profile(device_id="hello-bare")
    assert resolved.complete is False
    assert resolved.routing_hints.get("prefer_preset") is True
    ws = resolve_workspace_mm(device_id="hello-bare")
    assert ws["x"] == PRODUCT_WRITING_WORKSPACE_MM["x"]


def test_zero_workspace_profile_not_complete():
    from device_gateway.profiles import resolve_profile

    register_profile(
        DeviceProfile(
            device_id="zero-dev",
            profile_id="zero-ws",
            model="test",
            workspace_mm={"x": 0.0, "y": 0.0, "z": 0.0},
            max_feed=1000.0,
            max_path_points=100,
            capabilities=("run_path",),
            supported_fw_prefixes=("",),
        )
    )
    resolved = resolve_profile(device_id="zero-dev")
    assert resolved.complete is False
    ws = resolve_workspace_mm(device_id="zero-dev")
    assert ws["x"] == PRODUCT_WRITING_WORKSPACE_MM["x"]


def test_invalid_explicit_workspace_falls_back():
    ws = resolve_workspace_mm({"x": "nope", "y": 60.0, "z": 10.0})
    assert ws["x"] == DEFAULT_WORKSPACE_MM["x"]
    partial = resolve_workspace_mm({"x": 50.0})
    assert partial["x"] == DEFAULT_WORKSPACE_MM["x"]


def test_explicit_profile_object_wins():
    register_profile(
        DeviceProfile(
            device_id="",
            profile_id="custom-200",
            model="test",
            workspace_mm={"x": 200.0, "y": 150.0, "z": 40.0},
            max_feed=1000.0,
            max_path_points=100,
            capabilities=("run_path",),
            supported_fw_prefixes=("",),
        )
    )
    from device_gateway.profiles import resolve_profile

    resolved = resolve_profile(profile_id="custom-200", device_id="dev-a")
    ws = resolve_workspace_mm(profile=resolved.profile)
    assert ws["x"] == 200.0
    assert ws["y"] == 150.0


def test_explicit_workspace_overrides_all():
    ws = resolve_workspace_mm({"x": 50.0, "y": 60.0, "z": 10.0}, device_id="anything")
    assert ws == {"x": 50.0, "y": 60.0, "z": 10.0}


def test_render_svg_respects_explicit_workspace():
    from device_gateway.path_pipeline import render_svg_task

    result = render_svg_task("M 0 0 L 400 0", workspace_mm={"x": 100.0, "y": 100.0, "z": 20.0})
    assert result["workspace_mm"]["x"] == 100.0
    assert max(p["x"] for p in result["path"]) <= 100.0


def test_render_svg_uses_device_profile_workspace():
    from device_gateway.path_pipeline import render_svg_task

    register_profile(
        DeviceProfile(
            device_id="dev-small",
            profile_id="small-80",
            model="test",
            workspace_mm={"x": 80.0, "y": 80.0, "z": 20.0},
            max_feed=1000.0,
            max_path_points=100,
            capabilities=("run_path",),
            supported_fw_prefixes=("",),
        )
    )
    result = render_svg_task("M 0 0 L 400 0", device_id="dev-small")
    assert result["workspace_mm"]["x"] == 80.0
    assert max(p["x"] for p in result["path"]) <= 80.0
