"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


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
