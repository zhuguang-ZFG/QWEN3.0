from device_gateway.path_validator import validate_capability_params
from device_gateway.protocol_families import MotionErrorCode
from device_intelligence.safety import validate_profile_compatibility
from device_intelligence.schemas import DeviceProfile


def test_profile_safety_rejects_path_outside_workspace():
    profile = DeviceProfile(profile_id="small", model="small", workspace_mm={"x": 20, "y": 20, "z": 5})

    sanitized, error = validate_capability_params(
        "run_path",
        {"feed": 100, "path": [{"x": 21, "y": 1, "z": 0}]},
        profile=profile,
    )

    assert sanitized == {}
    assert error == MotionErrorCode.E_BAD_PARAMS.value


def test_profile_safety_rejects_feed_above_profile_cap():
    profile = DeviceProfile(profile_id="slow", model="slow", max_feed=300)

    sanitized, error = validate_capability_params(
        "run_path",
        {"feed": 301, "path": [{"x": 1, "y": 1, "z": 0}]},
        profile=profile,
    )

    assert sanitized == {}
    assert error == MotionErrorCode.E_BAD_PARAMS.value


def test_profile_safety_rejects_unsupported_firmware_prefix():
    profile = DeviceProfile(profile_id="prod", model="prod", supported_fw_prefixes=("u8-prod-",))

    assert validate_profile_compatibility(profile, "u8-test-1") == MotionErrorCode.E_UNSUPPORTED_PROFILE.value
    assert validate_profile_compatibility(profile, "u8-prod-2026") is None
