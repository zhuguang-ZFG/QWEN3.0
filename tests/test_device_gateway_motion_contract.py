#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motion protocol contracts: error codes, firmware matrix, FakeDevice negatives.

Aligned with fz software-fullchain design (L2a): contracts are first-class,
not empty enum smoke. Uses FakeDevice for behavioral negatives (no network).
"""

from __future__ import annotations

import pytest

from device_gateway.firmware_matrix import (
    COMPATIBILITY_MATRIX,
    get_supported_capabilities,
    is_capability_available,
)
from device_gateway.path_data import (
    MotionEventKind,
    MotionPoint,
    home_command,
    move_to_command,
    run_path_command,
)
from device_gateway.protocol_families import (
    ACTIVE_FAMILIES,
    FAMILY_ALLOWLISTS,
    MotionErrorCode,
    ProtocolFamily,
)
from device_gateway.safety import MAX_FEED, MAX_POINTS
from tests.helpers.fake_device import FakeDevice


def test_all_motion_error_codes_are_strings():
    for code in MotionErrorCode:
        assert isinstance(code.value, str)
        assert code.value.startswith("E_")
        assert code.name == code.value


def test_motion_error_code_set_is_stable():
    """Guard against silent renames that break cloud/device clients."""
    expected = {
        "E_UNSUPPORTED_CAPABILITY",
        "E_MISSING_PATH",
        "E_BAD_PARAMS",
        "E_U1_UNAVAILABLE",
        "E_DEVICE_UPDATING",
        "E_EXECUTION_FAILED",
        "E_UNSUPPORTED_BOARD",
        "E_UNSUPPORTED_PROFILE",
        "E_TIMEOUT",
    }
    assert {c.value for c in MotionErrorCode} == expected


def test_active_family_is_motion_only():
    assert ProtocolFamily.MOTION.value in ACTIVE_FAMILIES
    assert ProtocolFamily.DISPLAY.value not in ACTIVE_FAMILIES


def test_motion_allowlist_contains_core_caps():
    allow = FAMILY_ALLOWLISTS[ProtocolFamily.MOTION.value]
    for cap in ("run_path", "write_text", "home", "stop", "get_device_info"):
        assert cap in allow


@pytest.mark.parametrize(
    "fw,cap,expect",
    [
        ("v1.0.0", "draw_generated", False),
        ("v1.1.0", "draw_generated", True),
        ("v1.0.0", "run_path", True),
        ("v1.2.0", "draw_asset", True),
        ("v1.0.0", "draw_asset", False),
        ("v1.3.0", "estop", True),
        ("v1.2.0", "estop", False),
        ("v9.9.9", "home", False),  # unknown version → empty set
    ],
)
def test_firmware_matrix_capability(fw, cap, expect):
    assert is_capability_available(cap, fw) is expect


def test_matrix_versions_monotonic_core_caps():
    """Higher listed versions keep core motion caps from v1.0.0."""
    core = get_supported_capabilities("v1.0.0")
    for ver in ("v1.1.0", "v1.2.0", "v1.3.0"):
        assert core <= get_supported_capabilities(ver), ver


def test_matrix_keys_match_expected_versions():
    assert set(COMPATIBILITY_MATRIX.keys()) == {"v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0"}


def test_fake_device_missing_path_errors():
    dev = FakeDevice(device_id="c1")
    dev.handle_command(home_command())
    events = dev.handle_command(run_path_command([], feed=100))
    kinds = [e.kind for e in events]
    assert MotionEventKind.ERROR in kinds
    err = next(e for e in events if e.kind == MotionEventKind.ERROR)
    assert "path" in err.error.lower()


def test_fake_device_not_homed_blocks_move():
    dev = FakeDevice(device_id="c2")
    events = dev.handle_command(move_to_command(1, 1))
    assert any(e.kind == MotionEventKind.ERROR and "homed" in e.error.lower() for e in events)


def test_fake_device_path_too_many_points():
    dev = FakeDevice(device_id="c3")
    dev.handle_command(home_command())
    pts = [MotionPoint(float(i % 10), 0.0) for i in range(MAX_POINTS + 5)]
    events = dev.handle_command(run_path_command(pts, feed=100))
    assert any(e.kind == MotionEventKind.ERROR and "too many" in e.error.lower() for e in events)


def test_fake_device_bad_feed():
    dev = FakeDevice(device_id="c4")
    dev.handle_command(home_command())
    events = dev.handle_command(run_path_command([MotionPoint(1, 1)], feed=MAX_FEED + 1))
    assert any(e.kind == MotionEventKind.ERROR and "feed" in e.error.lower() for e in events)


def test_fake_device_run_path_happy():
    dev = FakeDevice(device_id="c5")
    dev.handle_command(home_command())
    events = dev.handle_command(run_path_command([MotionPoint(1, 2), MotionPoint(3, 4)], feed=200))
    kinds = [e.kind for e in events]
    assert MotionEventKind.ERROR not in kinds
    assert MotionEventKind.COMMAND_DONE in kinds


def test_unsupported_capability_contract_mapping():
    """Document expected cloud error when matrix denies capability."""
    assert not is_capability_available("draw_generated", "v1.0.0")
    # Gateway should surface this as E_UNSUPPORTED_CAPABILITY when wired;
    # contract keeps the code symbol stable for clients.
    assert MotionErrorCode.E_UNSUPPORTED_CAPABILITY.value == "E_UNSUPPORTED_CAPABILITY"
