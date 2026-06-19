"""Tests for device_gateway.family_approval_store."""

from __future__ import annotations

import pytest

import device_gateway.family_approval_store as store


@pytest.fixture(autouse=True)
def _isolate_family_approvals(tmp_path, monkeypatch):
    db_path = str(tmp_path / "family_approval.db")
    monkeypatch.setenv("LIMA_DB_PATH", db_path)
    store.set_db_path(db_path)
    store.reset_family_approvals()
    yield
    store.reset_family_approvals()


def test_approve_and_check_family():
    assert not store.is_family_approved("d-1", "display")
    record = store.approve_family("d-1", "display", approved_by="admin", evidence={"test": "ok"})
    assert record.status == "approved"
    assert record.approved_by == "admin"
    assert store.is_family_approved("d-1", "display")


def test_approve_overwrites_previous_revoked():
    store.approve_family("d-1", "audio", approved_by="admin")
    store.revoke_family("d-1", "audio", revoked_by="admin")
    assert not store.is_family_approved("d-1", "audio")
    store.approve_family("d-1", "audio", approved_by="admin", evidence={"rerun": True})
    assert store.is_family_approved("d-1", "audio")
    row = store.get_family_approval("d-1", "audio")
    assert row.evidence == {"rerun": True}
    assert row.revoked_at is None


def test_revoke_missing_returns_none():
    assert store.revoke_family("d-1", "speech", revoked_by="admin") is None


def test_list_family_approvals():
    store.approve_family("d-1", "display", approved_by="admin")
    store.approve_family("d-1", "audio", approved_by="admin")
    store.revoke_family("d-1", "audio", revoked_by="admin")
    approvals = store.list_family_approvals("d-1")
    assert len(approvals) == 2
    statuses = {a.family: a.status for a in approvals}
    assert statuses == {"audio": "revoked", "display": "approved"}


def test_get_family_approval_missing():
    assert store.get_family_approval("d-1", "ocr") is None
