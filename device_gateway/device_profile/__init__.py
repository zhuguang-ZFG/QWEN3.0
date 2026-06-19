"""Device profile routing inputs — hardware capability, preferences, and history.

Device profiles provide first-class routing signals that influence model and
backend selection.  Profiles come from two sources:

1. **Hello frame** — device reports its capabilities and preferences at connect.
2. **Route evidence inference** — historical routing artifacts (from
   artifact_recorder) are aggregated to build a history profile.

A profile includes capability constraints (compute level, memory, supported
features), preference hints (latency vs cost vs quality), and historical
telemetry (preferred models, failed backends, success rates).
"""

from __future__ import annotations

from device_gateway.device_profile.models import (
    COMPUTE_LEVELS,
    COST_SENSITIVITY_VALUES,
    PRIORITY_VALUES,
    DeviceCapability,
    DeviceHistory,
    DevicePreferences,
    DeviceProfile,
)
from device_gateway.device_profile.registry import (
    _device_profiles,
    get_device_profile,
    register_device_profile,
    reset_device_profiles_for_tests,
)
from device_gateway.device_profile.serialize import profile_from_dict, profile_to_dict
from device_gateway.device_profile.sources import infer_profile_from_artifacts, profile_from_hello_frame

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
