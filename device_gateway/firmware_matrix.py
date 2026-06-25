"""Firmware compatibility matrix — track firmware version × capability support."""

from __future__ import annotations

COMPATIBILITY_MATRIX: dict[str, frozenset[str]] = {
    "v1.0.0": frozenset({"write_text", "run_path", "home", "pause", "resume", "stop", "get_device_info"}),
    "v1.1.0": frozenset(
        {"write_text", "run_path", "home", "pause", "resume", "stop", "get_device_info", "draw_generated"}
    ),
    "v1.2.0": frozenset(
        {
            "write_text",
            "run_path",
            "home",
            "pause",
            "resume",
            "stop",
            "get_device_info",
            "draw_generated",
            "draw_asset",
            "self_check",
        }
    ),
    "v1.3.0": frozenset(
        {
            "write_text",
            "run_path",
            "home",
            "pause",
            "resume",
            "stop",
            "get_device_info",
            "draw_generated",
            "draw_asset",
            "self_check",
            "estop",
        }
    ),
}


def get_supported_capabilities(firmware_version: str) -> frozenset[str]:
    """返回固件支持的能力集。"""
    return COMPATIBILITY_MATRIX.get(firmware_version, frozenset())


def is_capability_available(capability: str, firmware_version: str) -> bool:
    """Return True if ``capability`` is supported by ``firmware_version``."""
    return capability in get_supported_capabilities(firmware_version)
