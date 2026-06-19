"""Backward-compatible facade for device_gateway.device_profile.

New code should import from ``device_gateway.device_profile`` directly; that
name now resolves to the ``device_gateway/device_profile/`` package and exports
the same public symbols.
"""

from __future__ import annotations

from device_gateway.device_profile import (
    COMPUTE_LEVELS,
    COST_SENSITIVITY_VALUES,
    PRIORITY_VALUES,
    DeviceCapability,
    DeviceHistory,
    DevicePreferences,
    DeviceProfile,
    _device_profiles,
    get_device_profile,
    infer_profile_from_artifacts,
    profile_from_dict,
    profile_from_hello_frame,
    profile_to_dict,
    register_device_profile,
    reset_device_profiles_for_tests,
)

__all__ = [
    "COMPUTE_LEVELS",
    "COST_SENSITIVITY_VALUES",
    "PRIORITY_VALUES",
    "DeviceCapability",
    "DeviceHistory",
    "DevicePreferences",
    "DeviceProfile",
    "_device_profiles",
    "get_device_profile",
    "infer_profile_from_artifacts",
    "profile_from_dict",
    "profile_from_hello_frame",
    "profile_to_dict",
    "register_device_profile",
    "reset_device_profiles_for_tests",
]
