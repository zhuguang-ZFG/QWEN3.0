"""In-memory registry of device profiles."""

from __future__ import annotations

from device_gateway.device_profile.models import DeviceProfile

# ── Storage for device profiles ──────────────────────────────────────────

_device_profiles: dict[str, DeviceProfile] = {}


# ── Public API ─────────────────────────────────────────────────────────────


def register_device_profile(profile: DeviceProfile) -> None:
    """Register a device profile so it's available for routing decisions."""
    _device_profiles[profile.device_id] = profile


def get_device_profile(device_id: str) -> DeviceProfile | None:
    """Look up a registered device profile by device_id."""
    return _device_profiles.get(device_id)


def reset_device_profiles_for_tests() -> None:
    """Clear all registered profiles (test isolation hook)."""
    _device_profiles.clear()
