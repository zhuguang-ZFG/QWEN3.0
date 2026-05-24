from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import routes.system_endpoints as system_endpoints
import server


def test_server_registers_extracted_system_endpoints():
    paths = {
        route.path
        for route in server.app.routes
        if isinstance(route, APIRoute)
    }

    assert "/v1/models" in paths
    assert "/health" in paths
    assert "/api/live-key" in paths
    assert "/v1/status" in paths
    assert server.health is system_endpoints.health
    assert server.router_status is system_endpoints.router_status


def test_health_uses_shared_loaded_modules():
    server._loaded_modules["unit_test_module"] = True

    client = TestClient(server.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["modules"]["unit_test_module"] is True
    server._loaded_modules.pop("unit_test_module", None)
