"""Tests for semantic firmware version comparison and fail-closed behavior."""

from __future__ import annotations

import pytest

from device_gateway._version_compare import parse_version
from device_protocol_registry import protocol_registry, ProtocolCompatibilityError


def test_parse_version_basic():
    assert parse_version("v1.10.0") == (1, 10, 0)
    assert parse_version("v1.9.0") == (1, 9, 0)


def test_semantic_compare_not_lexicographic():
    """v1.10.0 > v1.9.0 semantically (but not lexicographically)."""
    assert parse_version("v1.10.0") > parse_version("v1.9.0")


def test_firmware_status_outdated():
    assert protocol_registry.firmware_status("v0.9.0") == "outdated"


def test_firmware_status_compatible():
    assert protocol_registry.firmware_status("v1.10.0") == "compatible"


def test_assert_fail_closed_empty_fw():
    """Empty fw_rev should raise (fail-closed), not silently pass."""
    with pytest.raises(ProtocolCompatibilityError):
        protocol_registry.assert_firmware_compatible("")


def test_assert_compatible_high_version():
    protocol_registry.assert_firmware_compatible("v1.10.0")
