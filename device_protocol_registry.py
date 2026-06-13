"""Protocol registry — maps firmware versions to capabilities and constraints.

Defines the authoritative contract for what the LiMa cloud considers
"supported" for a given device firmware and protocol version.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ProtocolCompatibilityError(ValueError):
    """Raised when firmware does not meet minimum protocol requirements."""


@dataclass(frozen=True)
class ProtocolRegistry:
    protocol_version_str: str = "lima-device-v1"
    min_firmware_str: str = "v1.0.0"
    supported_capabilities: frozenset[str] = field(default_factory=lambda: frozenset({
        "run_path",
        "write_text",
        "draw_generated",
        "draw_asset",
        "home",
        "pause",
        "resume",
        "stop",
        "get_device_info",
        "self_check",
    }))
    deprecated_fields_set: frozenset[str] = field(default_factory=lambda: frozenset({"text"}))

    def protocol_version(self) -> str:
        return self.protocol_version_str

    def min_firmware(self) -> str:
        return self.min_firmware_str

    def is_capability_supported(self, capability: str) -> bool:
        return capability in self.supported_capabilities

    def deprecated_fields(self) -> frozenset[str]:
        return self.deprecated_fields_set

    def firmware_status(self, fw_rev: str) -> str:
        """Return firmware compatibility status.

        Returns:
            'compatible' — firmware meets minimum
            'outdated'   — firmware is below minimum
            'unknown'    — firmware string is empty
        """
        if not fw_rev:
            return "unknown"
        if fw_rev >= self.min_firmware_str:
            return "compatible"
        return "outdated"

    def assert_firmware_compatible(self, fw_rev: str) -> None:
        """Raise ProtocolCompatibilityError if firmware is too old."""
        if not fw_rev:
            return  # Empty = unknown device, allow through
        status = self.firmware_status(fw_rev)
        if status == "outdated":
            raise ProtocolCompatibilityError(
                f"firmware {fw_rev} is below minimum {self.min_firmware_str}; "
                "update required"
            )


protocol_registry = ProtocolRegistry()
