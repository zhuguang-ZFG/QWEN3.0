from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.events import semantic_cache_event
from observability.metrics import record, reset_metrics
from routes import admin_metrics
from routes.admin_auth import verify_admin


def test_admin_gray_metrics_requires_admin_token(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-secret")
    app = FastAPI()
    app.include_router(admin_metrics.router, prefix="/admin")

    client = TestClient(app)
    response = client.get("/admin/api/metrics/gray")
    assert response.status_code == 401


def test_admin_gray_metrics_returns_snapshot(monkeypatch):
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-secret")
    reset_metrics()
    record(semantic_cache_event("hit", latency_ms=10.0))
    record(semantic_cache_event("miss", latency_ms=20.0))

    app = FastAPI()
    app.dependency_overrides[verify_admin] = lambda: None
    app.include_router(admin_metrics.router, prefix="/admin")

    client = TestClient(app)
    response = client.get(
        "/admin/api/metrics/gray",
        headers={"Authorization": "Bearer admin-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["semantic_cache"]["hit"] == 1
    assert body["semantic_cache"]["miss"] == 1
    assert "avg_lookup_ms" in body["semantic_cache"]
    assert "instructor_intent" in body
