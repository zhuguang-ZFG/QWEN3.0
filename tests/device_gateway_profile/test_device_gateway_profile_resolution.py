"""Device profile resolution tests."""

from device_gateway.device_route_memory import reset_route_memory_for_tests
from device_gateway.profiles import (
    CONSERVATIVE_MAX_PATH_POINTS,
    CONSERVATIVE_WORKSPACE_MM,
    register_profile,
    reset_profiles_for_tests,
    resolve_profile,
)
from device_intelligence.schemas import DeviceProfile


def setup_function():
    reset_profiles_for_tests()
    reset_route_memory_for_tests()


def test_unknown_device_gets_conservative_profile():
    resolved = resolve_profile(device_id="dev-unknown")

    assert resolved.complete is False
    assert resolved.fw_compatible is True
    assert resolved.profile.max_path_points == CONSERVATIVE_MAX_PATH_POINTS
    assert resolved.profile.workspace_mm == CONSERVATIVE_WORKSPACE_MM
    assert resolved.routing_hints["prefer_preset"] is True
    assert resolved.routing_hints["downgrade_generated"] is True


def test_conservative_profile_has_simple_complexity():
    resolved = resolve_profile(device_id="dev-new")

    assert resolved.routing_hints["max_complexity"] == "simple"


def test_registered_profile_is_complete():
    profile = DeviceProfile(
        profile_id="u8-standard",
        model="U8",
        workspace_mm={"x": 100.0, "y": 100.0, "z": 20.0},
        max_feed=1200.0,
        max_path_points=200,
    )
    register_profile(profile)

    resolved = resolve_profile(profile_id="u8-standard", device_id="dev-1")

    assert resolved.complete is True
    assert resolved.profile.model == "U8"
    assert resolved.profile.max_path_points == 200
    assert resolved.routing_hints.get("downgrade_generated") is None
    assert resolved.routing_hints["max_complexity"] == "normal"


def test_registered_profile_not_found_falls_back_to_conservative():
    register_profile(DeviceProfile(profile_id="u8-standard", model="U8"))

    resolved = resolve_profile(profile_id="u8-pro", device_id="dev-2")

    assert resolved.complete is False
    assert resolved.profile.profile_id.startswith("conservative-")


def test_fw_compatible_with_empty_prefixes():
    profile = DeviceProfile(
        profile_id="u8-any",
        model="U8",
        supported_fw_prefixes=("",),
    )
    register_profile(profile)

    resolved = resolve_profile(profile_id="u8-any", fw_rev="v1.2.3")

    assert resolved.fw_compatible is True


def test_fw_incompatible_blocks_dispatch():
    profile = DeviceProfile(
        profile_id="u8-v2only",
        model="U8",
        supported_fw_prefixes=("v2.",),
    )
    register_profile(profile)

    resolved = resolve_profile(profile_id="u8-v2only", fw_rev="v1.0.0")

    assert resolved.fw_compatible is False
    assert resolved.routing_hints["block_dispatch"] is True
    assert resolved.routing_hints["block_reason"] == "firmware incompatible"


def test_fw_compatible_with_matching_prefix():
    profile = DeviceProfile(
        profile_id="u8-v2only",
        model="U8",
        supported_fw_prefixes=("v2.",),
    )
    register_profile(profile)

    resolved = resolve_profile(profile_id="u8-v2only", fw_rev="v2.1.0")

    assert resolved.fw_compatible is True


def test_unknown_fw_is_conservatively_compatible():
    profile = DeviceProfile(
        profile_id="u8-strict",
        model="U8",
        supported_fw_prefixes=("v2.",),
    )
    register_profile(profile)

    resolved = resolve_profile(profile_id="u8-strict", fw_rev="")

    assert resolved.fw_compatible is True


def test_shadow_profile_used_when_no_registered():
    shadow = {
        "profile_id": "shadow-u8",
        "model": "U8",
        "workspace_mm": {"x": 80.0, "y": 80.0, "z": 15.0},
        "max_feed": 800.0,
        "max_path_points": 150,
    }

    resolved = resolve_profile(device_id="dev-shadow", shadow_profile=shadow)

    assert resolved.profile.profile_id == "shadow-u8"
    assert resolved.profile.max_feed == 800.0
    # Shadow profile is not "complete" (only registered profiles are)
    assert resolved.complete is False


def test_empty_shadow_falls_back_to_conservative():
    resolved = resolve_profile(device_id="dev-empty", shadow_profile={})

    assert resolved.complete is False
    assert resolved.profile.profile_id.startswith("conservative-")
