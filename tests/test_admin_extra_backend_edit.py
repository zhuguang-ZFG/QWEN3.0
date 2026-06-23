"""Tests for routes/admin_extra_backend_edit.py — backend mutation endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routes.admin_extra_backend_edit import router as backend_edit_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(backend_edit_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify
app.dependency_overrides[admin_auth.verify_csrf] = _noop_verify


class TestAdminEditBackend:
    def test_backend_not_found(self):
        client = TestClient(app)
        with patch("routes.admin_extra_backend_edit.BACKENDS", {}):
            response = client.put("/api/backends/missing", json={"url": "https://x.com"})
            assert response.status_code == 404

    def test_update_url_and_model(self):
        client = TestClient(app)
        backends = {"groq": {"url": "old", "model": "old-model"}}
        with patch("routes.admin_extra_backend_edit.BACKENDS", backends):
            response = client.put("/api/backends/groq", json={"url": "https://new.com", "model": "new-model"})
            assert response.status_code == 200
            assert backends["groq"]["url"] == "https://new.com"
            assert backends["groq"]["model"] == "new-model"

    def test_update_caps(self):
        client = TestClient(app)
        backends = {"groq": {"url": "https://x.com", "model": "m", "caps": []}}
        with patch("routes.admin_extra_backend_edit.BACKENDS", backends):
            response = client.put("/api/backends/groq", json={"caps": ["chat"]})
            assert response.status_code == 200
            assert backends["groq"]["caps"] == ["chat"]
