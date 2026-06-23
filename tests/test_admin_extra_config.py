"""Tests for routes/admin_extra_config.py — config import URL safety."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routes.admin_extra_config import router as config_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(config_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify
app.dependency_overrides[admin_auth.verify_csrf] = _noop_verify


class TestConfigImport:
    def test_rejects_missing_version(self):
        client = TestClient(app)
        response = client.post("/api/config/import", json={})
        assert response.status_code == 400

    def test_rejects_http_url(self):
        client = TestClient(app)
        body = {
            "version": "1.0",
            "backends": {"bad": {"url": "http://example.com"}},
        }
        response = client.post("/api/config/import", json=body)
        assert response.status_code == 400
        assert "unsafe" in response.text.lower()

    def test_accepts_https_url(self):
        client = TestClient(app)
        body = {
            "version": "1.0",
            "backends": {"good": {"url": "https://api.example.com"}},
        }
        with patch("routes.admin_extra_config.has_backend", return_value=False):
            with patch("routes.admin_extra_config.add_backend") as mock_add:
                with patch("routes.admin_extra_config._is_safe_backend_url", return_value=True):
                    response = client.post("/api/config/import", json=body)
                    assert response.status_code == 200
                    mock_add.assert_called_once()
