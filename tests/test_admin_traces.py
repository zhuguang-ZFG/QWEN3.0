from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.metrics import record_trace, reset_traces
from routes import admin_traces
from routes.admin_auth import verify_admin


def test_admin_recent_traces_returns_recorded_traces(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-secret")
    reset_traces()
    record_trace({"trace_id": "abc123", "spans": []})

    app = FastAPI()
    app.dependency_overrides[verify_admin] = lambda: None
    app.include_router(admin_traces.router, prefix="/admin")

    client = TestClient(app)
    response = client.get("/admin/api/traces/recent?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert len(body["traces"]) == 1
    assert body["traces"][0]["trace_id"] == "abc123"
