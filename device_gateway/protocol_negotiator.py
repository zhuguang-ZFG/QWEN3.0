"""Protocol version negotiation — device connects, server picks best version."""

from __future__ import annotations

SUPPORTED_PROTOCOLS = ["lima-device-v1", "lima-device-v2-draft"]


class ProtocolNegotiator:
    """Negotiate a mutually supported device-gateway protocol version."""

    def negotiate(self, device_protocol: str, firmware_version: str) -> str:
        """选择双方支持的最高协议版本。

        The server supports a fixed ordered list of protocols.  If the device
        advertises a supported version, use it; otherwise fall back to the
        baseline version so legacy clients remain compatible.

        Args:
            device_protocol: Protocol version reported by the device.
            firmware_version: Device firmware revision (reserved for future
                firmware-aware negotiation).

        Returns:
            The negotiated protocol version string.
        """
        del firmware_version  # reserved for future firmware-aware negotiation
        if device_protocol in SUPPORTED_PROTOCOLS:
            return device_protocol
        return "lima-device-v1"  # fallback

    def capabilities_for_version(self, protocol_version: str) -> frozenset[str]:
        """返回该协议版本支持的能力集。"""
        if protocol_version == "lima-device-v2-draft":
            return frozenset(
                {
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
                    "estop",
                    "voice_command",  # v2 新增
                    "multi_pass",
                    "variable_speed",  # v2 新增
                }
            )
        return frozenset(
            {
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
            }
        )
