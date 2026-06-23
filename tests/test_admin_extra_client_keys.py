"""Tests for routes/admin_extra_client_keys.py — client API key management."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_extra_client_keys import router as client_keys_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(client_keys_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify
app.dependency_overrides[admin_auth.verify_csrf] = _noop_verify


class TestClientKeys:
    def test_list_empty(self):
        client = TestClient(app)
        response = client.get("/api/client-keys")
        assert response.status_code == 200
        assert response.json()["keys"] == []

    def test_create_requires_label(self):
        client = TestClient(app)
        response = client.post("/api/client-keys", json={})
        assert response.status_code == 400

    def test_create_and_list(self):
        client = TestClient(app)
        response = client.post("/api/client-keys", json={"label": "test"})
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["key"]["label"] == "test"
        assert "key_masked" in data["key"]
