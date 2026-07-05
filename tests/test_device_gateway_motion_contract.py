"""Tests for device_gateway motion error codes (protocol_families)."""

from device_gateway.protocol_families import MotionErrorCode


def test_all_motion_error_codes_are_strings():
    for code in MotionErrorCode:
        assert isinstance(code.value, str)
        assert code.value.startswith("E_")
