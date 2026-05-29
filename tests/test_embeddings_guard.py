from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server
from access_guard import require_private_api_key


def _route_for(path: str, method: str) -> APIRoute:
    for route in server.app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"route not found: {method} {path}")


def test_embeddings_requires_private_api_key_dependency():
    route = _route_for("/v1/embeddings", "POST")
    dependency_calls = [dep.call for dep in route.dependant.dependencies]
    assert require_private_api_key in dependency_calls


def test_embeddings_rejects_unauthenticated_request(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    client = TestClient(server.app)
    response = client.post("/v1/embeddings", json={"input": "hello"})
    assert response.status_code == 401


def test_embeddings_fail_closed_without_configured_keys(monkeypatch):
    monkeypatch.delenv("LIMA_API_KEY", raising=False)
    monkeypatch.delenv("LIMA_API_KEYS", raising=False)
    client = TestClient(server.app)
    response = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer anything"},
        json={"input": "hello"},
    )
    assert response.status_code == 503
