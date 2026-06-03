"""Tests for client API key management."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    """Ensure clean state for each test."""
    import routes.admin_client_keys as ck_mod

    # Use a temp file for keys storage
    test_keys_path = tmp_path / "client_keys.json"
    test_keys_path.write_text(json.dumps({"keys": []}), encoding="utf-8")
    monkeypatch.setattr(ck_mod, "_KEYS_PATH", test_keys_path)
    monkeypatch.setattr(ck_mod, "_DATA_DIR", tmp_path)
    ck_mod._usage.clear()
    yield


def _create_key(label="test-key", **overrides):
    """Helper: create a client key via the module functions."""
    import routes.admin_client_keys as ck_mod

    token = ck_mod._generate_key_value()
    now = time.time()
    key_record = {
        "key_id": ck_mod._key_id(token),
        "key_value": token,
        "label": label,
        "enabled": True,
        "created_at": now,
        "last_used_at": None,
        "request_count": 0,
        "quota_daily": overrides.get("quota_daily", 1000),
        "quota_monthly": overrides.get("quota_monthly", 30000),
        "rate_limit_rpm": overrides.get("rate_limit_rpm", 20),
        "allowed_urls": overrides.get("allowed_urls", ["*"]),
    }
    with ck_mod._lock:
        keys = ck_mod._load_keys()
        keys.append(key_record)
        ck_mod._save_keys(keys)
    return token, key_record["key_id"]


# ── Key Generation ──────────────────────────────────────────────────────────


def test_generate_key_format():
    import routes.admin_client_keys as ck_mod

    token = ck_mod._generate_key_value()
    assert token.startswith("lima-")
    # Format: lima-XXXXXXXX-XXXXXXXX-XXXXXXXXXXXXXXXX
    parts = token.split("-")
    assert parts[0] == "lima"
    assert len(parts) == 4


def test_generate_key_uniqueness():
    import routes.admin_client_keys as ck_mod

    tokens = {ck_mod._generate_key_value() for _ in range(100)}
    assert len(tokens) == 100


def test_key_id_generation():
    import routes.admin_client_keys as ck_mod

    kid = ck_mod._key_id("lima-abcdef01-23456789-abcd1234")
    assert kid.startswith("ck-")
    assert len(kid) > 15


# ── Key Masking ─────────────────────────────────────────────────────────────


def test_mask_key_long():
    import routes.admin_client_keys as ck_mod

    masked = ck_mod._mask_key("lima-abcdef01-23456789-abcd1234")
    assert masked.startswith("lima-abcde")
    assert masked.endswith("1234")
    assert "****" in masked


def test_mask_key_empty():
    import routes.admin_client_keys as ck_mod

    assert ck_mod._mask_key("") == ""


# ── Storage CRUD ────────────────────────────────────────────────────────────


def test_load_keys_empty():
    import routes.admin_client_keys as ck_mod

    keys = ck_mod._load_keys()
    assert keys == []


def test_save_and_load():
    import routes.admin_client_keys as ck_mod

    token, kid = _create_key("my-label")
    keys = ck_mod._load_keys()
    assert len(keys) == 1
    assert keys[0]["label"] == "my-label"
    assert keys[0]["key_value"] == token


def test_find_client_key():
    import routes.admin_client_keys as ck_mod

    token, kid = _create_key("find-me")
    found = ck_mod.find_client_key(token)
    assert found is not None
    assert found["label"] == "find-me"


def test_find_client_key_not_found():
    import routes.admin_client_keys as ck_mod

    found = ck_mod.find_client_key("nonexistent-key")
    assert found is None


# ── Quota Checking ──────────────────────────────────────────────────────────


def test_check_quota_enabled():
    import routes.admin_client_keys as ck_mod

    _create_key("quota-test")
    keys = ck_mod._load_keys()
    assert ck_mod.check_key_quota(keys[0]) is True


def test_check_quota_disabled():
    import routes.admin_client_keys as ck_mod

    _create_key("disabled-test", quota_daily=100)
    keys = ck_mod._load_keys()
    keys[0]["enabled"] = False
    with ck_mod._lock:
        ck_mod._save_keys(keys)
    assert ck_mod.check_key_quota(keys[0]) is False


def test_check_quota_exceeded():
    import routes.admin_client_keys as ck_mod

    token, kid = _create_key("exceeded-test", quota_daily=5)
    keys = ck_mod._load_keys()
    key_rec = keys[0]

    # Simulate 5 requests
    for _ in range(5):
        ck_mod.record_key_usage(token)

    assert ck_mod.check_key_quota(key_rec) is False


def test_check_quota_unlimited():
    import routes.admin_client_keys as ck_mod

    _create_key("unlimited-test", quota_daily=0)
    keys = ck_mod._load_keys()
    assert ck_mod.check_key_quota(keys[0]) is True


# ── Usage Recording ─────────────────────────────────────────────────────────


def test_record_usage_increments():
    import routes.admin_client_keys as ck_mod

    token, _ = _create_key("usage-test")
    ck_mod.record_key_usage(token)
    ck_mod.record_key_usage(token)
    summary = ck_mod.get_key_usage_summary(token)
    assert summary["daily_count"] == 2
    assert summary["monthly_count"] == 2
    assert summary["last_used_at"] is not None


# ── API Integration ─────────────────────────────────────────────────────────


def _mock_verify_admin():
    """Dependency override that skips admin auth."""
    return None


def _mock_verify_csrf():
    """Dependency override that skips CSRF check."""
    return None


def _make_app():
    """Create a FastAPI app with auth overrides for testing."""
    from fastapi import FastAPI
    from routes.admin_client_keys import router
    from routes.admin_auth import verify_admin, verify_csrf

    app = FastAPI()
    app.dependency_overrides[verify_admin] = _mock_verify_admin
    app.dependency_overrides[verify_csrf] = _mock_verify_csrf
    app.include_router(router)
    return app


def test_api_list_keys_empty():
    """Test list endpoint returns empty list initially."""
    from fastapi.testclient import TestClient

    app = _make_app()
    client = TestClient(app)
    resp = client.get("/admin/api/client-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert data["keys"] == []
    assert data["total"] == 0


def test_api_create_and_list():
    """Test creating a key and listing it."""
    from fastapi.testclient import TestClient

    app = _make_app()
    client = TestClient(app)

    # Create
    resp = client.post("/admin/api/client-keys", json={
        "label": "cursor-user",
        "quota_daily": 500,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["key_value"].startswith("lima-")

    # List
    resp = client.get("/admin/api/client-keys")
    assert resp.status_code == 200
    keys = resp.json()["keys"]
    assert len(keys) == 1
    assert keys[0]["label"] == "cursor-user"
    assert keys[0]["quota_daily"] == 500


def test_api_create_requires_label():
    """Test that creating a key without label fails."""
    from fastapi.testclient import TestClient

    app = _make_app()
    client = TestClient(app)

    resp = client.post("/admin/api/client-keys", json={})
    assert resp.status_code == 400


def test_api_delete_key():
    """Test deleting a key."""
    from fastapi.testclient import TestClient

    app = _make_app()
    client = TestClient(app)

    # Create
    resp = client.post("/admin/api/client-keys", json={"label": "to-delete"})
    kid = resp.json()["key_id"]

    # Delete
    resp = client.delete(f"/admin/api/client-keys/{kid}")
    assert resp.status_code == 200

    # Verify gone
    resp = client.get("/admin/api/client-keys")
    assert resp.json()["total"] == 0


def test_api_toggle_key():
    """Test enabling/disabling a key."""
    from fastapi.testclient import TestClient

    app = _make_app()
    client = TestClient(app)

    resp = client.post("/admin/api/client-keys", json={"label": "toggle-test"})
    kid = resp.json()["key_id"]

    # Disable
    resp = client.put(f"/admin/api/client-keys/{kid}", json={"enabled": False})
    assert resp.status_code == 200

    # Verify disabled
    resp = client.get("/admin/api/client-keys")
    key = resp.json()["keys"][0]
    assert key["enabled"] is False
