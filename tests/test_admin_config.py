"""Tests for config import/export endpoints (Phase 1.3)."""

import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LIMA_ADMIN_TOKEN"] = "test-admin-token"

from routes.admin_api import (
    _ADMIT_PATH,
    _OVERLAY_PATH,
)
from routes.admin_api import (
    router as admin_api_router,
)
from routes.admin_auth import verify_admin, verify_csrf

app = FastAPI()
app.dependency_overrides[verify_admin] = lambda: None
app.dependency_overrides[verify_csrf] = lambda: None
app.include_router(admin_api_router, prefix="/admin")
client = TestClient(app)
HEADERS = {"Authorization": "Bearer test-admin-token"}

# Separate client WITHOUT auth overrides — used for auth-required tests
_raw_app = FastAPI()
_raw_app.include_router(admin_api_router, prefix="/admin")
raw_client = TestClient(_raw_app)


def test_config_export_requires_auth():
    resp = raw_client.get("/admin/api/config/export")
    assert resp.status_code in (401, 403)


def test_config_export_returns_json():
    resp = client.get("/admin/api/config/export", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "1.0"
    assert "exported_at" in data
    assert "backend_overrides" in data
    assert "backend_admission" in data


def test_config_import_roundtrip():
    """Export, modify, import, then export again should match."""
    payload = {
        "version": "1.0",
        "backend_overrides": {"add": {"test_backend": {"url": "http://test", "key": "none"}}},
        "backend_admission": {"test_backend": "code_medium_candidate"},
    }
    resp = client.post(
        "/admin/api/config/import",
        json=payload,
        headers=HEADERS,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "backend_overrides" in resp.json()["imported"]
    assert "backend_admission" in resp.json()["imported"]

    # Verify the files were written
    assert _OVERLAY_PATH.exists()
    assert _ADMIT_PATH.exists()

    # Re-export and verify content matches
    resp2 = client.get("/admin/api/config/export", headers=HEADERS)
    exported = resp2.json()
    assert exported["backend_overrides"]["add"]["test_backend"]["url"] == "http://test"
    assert exported["backend_admission"]["test_backend"] == "code_medium_candidate"


def test_config_import_rejects_wrong_version():
    payload = {"version": "99.0", "backend_overrides": {}}
    resp = client.post(
        "/admin/api/config/import",
        json=payload,
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_config_import_partial_import():
    """Importing only backend_overrides should not touch admission."""
    original_admit = _ADMIT_PATH.read_text(encoding="utf-8") if _ADMIT_PATH.exists() else None
    try:
        payload = {
            "version": "1.0",
            "backend_overrides": {"add": {}},
        }
        resp = client.post(
            "/admin/api/config/import",
            json=payload,
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["imported"] == ["backend_overrides"]
    finally:
        # Restore original admission file if it existed
        if original_admit is not None:
            _ADMIT_PATH.write_text(original_admit, encoding="utf-8")
