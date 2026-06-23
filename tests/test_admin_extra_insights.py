"""Tests for routes/admin_extra_insights.py — admin insights endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.admin_extra_insights import router as insights_router
from routes import admin_auth


async def _noop_verify():
    return None


app = FastAPI()
app.include_router(insights_router)
app.dependency_overrides[admin_auth.verify_admin] = _noop_verify


class TestInsights:
    def test_fallback_analysis(self):
        client = TestClient(app)
        response = client.get("/api/fallback-analysis")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_backend" in data

    def test_key_url_inventory(self):
        client = TestClient(app)
        response = client.get("/api/key-url-inventory")
        assert response.status_code == 200
        assert "backends" in response.json()

    def test_retrain_jobs(self):
        client = TestClient(app)
        response = client.get("/api/retrain/jobs")
        assert response.status_code == 200
        assert response.json()["jobs"] == []

    def test_trigger_retrain(self):
        client = TestClient(app)
        response = client.post("/api/retrain")
        assert response.status_code == 200
        assert response.json()["status"] == "retired"

    def test_agent_audit(self):
        client = TestClient(app)
        response = client.get("/api/agent-audit")
        assert response.status_code == 200
        assert response.json()["tasks"] == []
