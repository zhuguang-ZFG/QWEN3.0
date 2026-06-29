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


def test_models_dynamic_from_backends_registry(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(
        system_endpoints,
        "BACKENDS",
        {
            "groq_llama": {"model": "llama-3.3-70b"},
            "openrouter_gpt": {"model": "openai/gpt-4.1"},
            "no_model_backend": {},
        },
    )
    client = TestClient(server.app)
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 200
    payload = response.json()
    ids = {m["id"] for m in payload["data"]}
    assert "llama-3.3-70b" in ids
    assert "openai/gpt-4.1" in ids
    owned_by = {m["id"]: m["owned_by"] for m in payload["data"]}
    assert owned_by["openai/gpt-4.1"] == "openai"
    assert owned_by["llama-3.3-70b"] == "meta"


def test_models_dedup_duplicate_model_ids(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(
        system_endpoints,
        "BACKENDS",
        {
            "provider_a": {"model": "shared-model"},
            "provider_b": {"model": "shared-model"},
        },
    )
    client = TestClient(server.app)
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-key"})
    data = response.json()["data"]
    assert sum(1 for m in data if m["id"] == "shared-model") == 1


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


def test_health_uses_shared_loaded_modules(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    try:
        system_endpoints._loaded_modules["unit_test_module"] = True

        client = TestClient(server.app)
        response = client.get("/health", headers={"Authorization": "Bearer test-key"})

        assert response.status_code == 200
        assert response.json()["modules"]["unit_test_module"] is True
    finally:
        system_endpoints._loaded_modules.pop("unit_test_module", None)


def test_health_anonymous_omits_internal_details(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(
        system_endpoints.server_lifespan,
        "get_startup_state",
        lambda: {"status": "ready", "errors": [], "pending_warm": []},
    )

    client = TestClient(server.app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"status", "version", "model", "startup"}
    assert set(payload["startup"].keys()) == {"status"}
    assert "modules" not in payload
    assert "security" not in payload


def test_health_returns_503_when_startup_status_is_error(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(
        system_endpoints.server_lifespan,
        "get_startup_state",
        lambda: {"status": "error", "errors": [{"phase": "unit", "error": "boom"}]},
    )
    monkeypatch.setattr(system_endpoints.server_lifespan, "STARTUP_PHASES", [])

    client = TestClient(server.app)
    response = client.get("/health", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["startup"]["errors"] == []
    assert response.json()["startup"]["error_count"] == 1
    assert response.json()["startup"]["error_phases"] == ["unit"]


def test_health_includes_anonymous_access_security_when_authenticated(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_ALLOW_ANONYMOUS", "1")
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")

    client = TestClient(server.app)
    response = client.get("/health", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    security = response.json()["security"]["anonymous_access"]
    assert security["env_enabled"] is True
    assert security["production_blocked"] is False
    assert security["allowed"] is True


def _mock_startup_state(monkeypatch, status: str, pending_warm: list | None = None, errors: list | None = None):
    monkeypatch.setattr(
        system_endpoints.server_lifespan,
        "get_startup_state",
        lambda: {
            "status": status,
            "pending_warm": pending_warm or [],
            "errors": errors or [],
        },
    )


def test_health_ready_returns_200_when_ready(monkeypatch):
    _mock_startup_state(monkeypatch, "ready")
    client = TestClient(server.app)
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["startup_status"] == "ready"


def test_health_ready_returns_503_when_warming(monkeypatch):
    _mock_startup_state(monkeypatch, "warming", pending_warm=["backend_profile.load"])
    client = TestClient(server.app)
    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["startup_status"] == "warming"
    assert payload["pending_warm"] == ["backend_profile.load"]


def test_health_ready_returns_503_when_error(monkeypatch):
    _mock_startup_state(monkeypatch, "error", errors=["boom"])
    client = TestClient(server.app)
    response = client.get("/health/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["startup_status"] == "error"
    assert payload["error_count"] == 1
