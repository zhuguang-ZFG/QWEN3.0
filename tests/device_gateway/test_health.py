from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.device_gateway import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_device_gateway_health_reports_protocol_and_auth_state():
    response = _client().get("/device/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["protocol"] == "lima-device-v1"
    assert data["auth_configured"] is True
    assert data["task_store"] == {"backend": "memory", "shared_across_processes": False}


def test_device_gateway_health_reports_unready_in_production_without_shared_state(monkeypatch):
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    response = _client().get("/device/v1/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["production_ready"] is False
