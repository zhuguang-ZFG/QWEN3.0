"""Backward-compatible re-export — canonical implementation in device_logic.payloads."""

from device_logic.payloads import (
    device_payload,
    member_payload,
    self_check_payload,
    supply_payload,
    task_payload,
    transfer_payload,
    voiceprint_payload,
)

__all__ = [
    "device_payload",
    "member_payload",
    "self_check_payload",
    "supply_payload",
    "task_payload",
    "transfer_payload",
    "voiceprint_payload",
]
