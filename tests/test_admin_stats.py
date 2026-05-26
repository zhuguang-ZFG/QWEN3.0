"""Admin stats tolerance for legacy backend_calls shapes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_api
from routes.admin_auth import verify_admin
from routes.admin_state import stats_context


def test_admin_stats_tolerates_integer_backend_calls(monkeypatch):
    stats, lock, enabled = stats_context()
    with lock:
        stats["start_time"] = 0
        stats["total_requests"] = 3
        stats["backend_calls"] = {"legacy_backend": 2, "modern_backend": {"count": 1, "total_ms": 40}}
        stats["intent_distribution"] = {}
        stats["recent_logs"] = []

    monkeypatch.setattr(admin_api, "stats_context", lambda: (stats, lock, enabled))

    app = FastAPI()
    app.dependency_overrides[verify_admin] = lambda: None
    app.include_router(admin_api.router, prefix="/admin")

    client = TestClient(app)
    response = client.get("/admin/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["backend_calls"]["legacy_backend"]["count"] == 2
    assert body["backend_calls"]["modern_backend"]["total_ms"] == 40
