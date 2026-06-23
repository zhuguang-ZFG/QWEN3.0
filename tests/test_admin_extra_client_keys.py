"""Tests for routes/admin_extra_client_keys.py — client API key management."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_extra_client_keys import router as client_keys_router
from routes import admin_auth
from routes import client_keys_store


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


class TestClientKeysPersistence:
    def test_key_survives_store_reload(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "client_keys.db")
        client_keys_store.set_db_path_for_tests(db_path)
        monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path))

        client = TestClient(app)
        response = client.post("/api/client-keys", json={"label": "persisted"})
        assert response.status_code == 200
        created = response.json()["key"]

        reloaded = client_keys_store.load_keys()
        assert created["key_id"] in reloaded
        assert reloaded[created["key_id"]]["label"] == "persisted"
