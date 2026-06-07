from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server
from access_guard import require_private_api_key


def _route_for(path: str, method: str) -> APIRoute:
    for route in server.app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


def test_agent_execute_routes_require_private_api_key_dependency():
    for path, method in (
        ("/agent/execute", "POST"),
        ("/agent/execute/status", "GET"),
    ):
        route = _route_for(path, method)
        dependency_calls = [dep.call for dep in route.dependant.dependencies]
        assert require_private_api_key in dependency_calls


def test_agent_execute_rejects_unauthenticated_request(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    client = TestClient(server.app)

    response = client.post("/agent/execute", json={"task": "echo ok"})

    assert response.status_code == 401
