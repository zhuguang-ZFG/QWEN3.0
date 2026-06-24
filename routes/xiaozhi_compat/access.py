"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from device_logic.access import (
    device_access,
    expire_pending_transfers,
    is_owner,
    parse_supply_updates,
    require_device_access,
)

__all__ = [
    "device_access",
    "expire_pending_transfers",
    "is_owner",
    "parse_supply_updates",
    "require_device_access",
]
