from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server
from access_guard import require_private_api_key
import routes.embeddings as embeddings_mod


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


def test_embeddings_rejects_invalid_bounds(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("JINA_API_KEY", "jina-test-key")
    client = TestClient(server.app)

    response = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer test-key"},
        json={"input": ["hello"], "dimensions": 0},
    )

    assert response.status_code == 400
    assert "dimensions" in response.json()["error"]


def test_embeddings_uses_async_http_client(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"embedding": [0.1]}]}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, *, json, headers):
            calls["url"] = url
            calls["json"] = json
            calls["headers"] = headers
            return FakeResponse()

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("JINA_API_KEY", "jina-test-key")
    monkeypatch.setattr(embeddings_mod.httpx, "AsyncClient", FakeAsyncClient)

    client = TestClient(server.app)
    response = client.post(
        "/v1/embeddings",
        headers={"Authorization": "Bearer test-key"},
        json={"input": "hello", "dimensions": 8},
    )

    assert response.status_code == 200
    assert calls["json"] == {"model": "jina-embeddings-v3", "input": ["hello"], "dimensions": 8}
    assert calls["headers"]["Authorization"] == "Bearer jina-test-key"
