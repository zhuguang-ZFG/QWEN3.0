"""Backward-compatible re-export — canonical implementation in device_logic.access."""

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
