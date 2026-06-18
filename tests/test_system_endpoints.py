from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import routes.system_endpoints as system_endpoints
import server
from access_guard import require_private_api_key


def _route_for(path: str, method: str) -> APIRoute:
    for route in server.app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


def test_server_registers_extracted_system_endpoints():
    paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}

    assert "/v1/models" in paths
    assert "/health" in paths
    assert "/api/live-key" in paths
    assert "/v1/status" in paths
    assert server.health is system_endpoints.health
    assert server.router_status is system_endpoints.router_status


def test_models_requires_private_api_key_dependency():
    route = _route_for("/v1/models", "GET")
    dependency_calls = [dep.call for dep in route.dependant.dependencies]
    assert require_private_api_key in dependency_calls


def test_models_rejects_unauthenticated_request(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    client = TestClient(server.app)
    response = client.get("/v1/models")
    assert response.status_code == 401


def test_models_accepts_bearer_token(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    client = TestClient(server.app)
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    assert response.json()["object"] == "list"


def test_live_key_returns_metadata_not_raw_provider_key(monkeypatch):
    secret = "sk-google-test-secret-do-not-leak"
    monkeypatch.setenv("GOOGLE_AI_KEY", secret)
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    client = TestClient(server.app)
    response = client.get(
        "/api/live-key",
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("available") is True
    assert "key" not in payload
    assert secret not in response.text


def test_health_uses_shared_loaded_modules():
    try:
        system_endpoints._loaded_modules["unit_test_module"] = True

        client = TestClient(server.app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["modules"]["unit_test_module"] is True
    finally:
        system_endpoints._loaded_modules.pop("unit_test_module", None)
