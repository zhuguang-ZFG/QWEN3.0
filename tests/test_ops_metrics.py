from fastapi import FastAPI
from fastapi.testclient import TestClient

import server
from routes.ops_metrics import router


def test_ops_metrics_reads_starlette_app_state(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    app = FastAPI()
    app.state.stats = {
        "total_requests": 3,
        "backend_calls": {"backend-a": 2, "backend-b": 1},
        "start_time": 1,
    }
    app.include_router(router)

    response = TestClient(app).get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-private-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] == 3
    assert data["backend_calls"] == {"backend-a": 2, "backend-b": 1}
    assert "device_gateway" in data
    assert "agent_workers" in data


def test_server_exposes_stats_to_ops_metrics_router():
    assert server.app.state.stats is server._stats
