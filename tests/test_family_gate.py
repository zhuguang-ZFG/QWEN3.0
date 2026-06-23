"""Tests for device_gateway.family_approval_store gating behavior."""

from __future__ import annotations

import pytest

from config.sqlite_pool import pool_clear

import device_gateway.family_approval_store as store
from device_gateway.family_approval_store import validate_family_capability
from device_gateway.protocol_families import ProtocolFamily


@pytest.fixture(autouse=True)
def _isolate_family_approvals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "family_gate.db")
    monkeypatch.setenv("LIMA_DB_PATH", db_path)
    store.set_db_path(db_path)
    store.reset_family_approvals()
    yield
    store.reset_family_approvals()
    pool_clear()


def test_motion_family_does_not_require_approval():
    allowed, error = validate_family_capability("d-1", ProtocolFamily.MOTION, "run_path")
    assert allowed is True
    assert error is None


def test_gated_family_requires_approval():
    allowed, error = validate_family_capability("d-1", ProtocolFamily.DISPLAY, "show_text")
    assert allowed is False
    assert "not approved" in error


def test_gated_family_allowed_after_approval():
    store.approve_family("d-1", "display", approved_by="admin")
    allowed, error = validate_family_capability("d-1", ProtocolFamily.DISPLAY, "show_text")
    assert allowed is True
    assert error is None


def test_gated_family_revoked_approval_blocked():
    store.approve_family("d-1", "audio", approved_by="admin")
    store.revoke_family("d-1", "audio", revoked_by="admin")
    allowed, error = validate_family_capability("d-1", ProtocolFamily.AUDIO, "play_audio")
    assert allowed is False
    assert "not approved" in error


def test_unknown_capability_rejected():
    allowed, error = validate_family_capability("d-1", ProtocolFamily.MOTION, "laser_engrave")
    assert allowed is False
    assert "not in family" in error


def test_unknown_family_rejected():
    allowed, error = validate_family_capability("d-1", "nuclear", "fusion")
    assert allowed is False
    assert "not in family" in error
