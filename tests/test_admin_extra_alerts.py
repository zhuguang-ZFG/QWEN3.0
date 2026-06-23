"""Tests for routes/admin_extra_alerts.py — alert rule CRUD."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_extra_alerts import router as alerts_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(alerts_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify
app.dependency_overrides[admin_auth.verify_csrf] = _noop_verify


class TestAlertRules:
    def test_list_empty(self):
        client = TestClient(app)
        response = client.get("/api/alerts/rules")
        assert response.status_code == 200
        assert response.json()["rules"] == []

    def test_create_requires_name(self):
        client = TestClient(app)
        response = client.post("/api/alerts/rules", json={})
        assert response.status_code == 400

    def test_create_and_list(self):
        client = TestClient(app)
        response = client.post("/api/alerts/rules", json={"name": "high_error"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "high_error"
        assert data["enabled"] is True
