"""Activation code state machine — re-export from device_logic."""

from device_logic.activation import (
    ACTIVATION_TTL_SECONDS,
    check_activation_code,
    new_activation_code,
    reset_activation_store_for_tests,
)

__all__ = [
    "ACTIVATION_TTL_SECONDS",
    "check_activation_code",
    "new_activation_code",
    "reset_activation_store_for_tests",
]
