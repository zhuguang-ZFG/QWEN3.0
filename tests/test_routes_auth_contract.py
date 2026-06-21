"""Auth boundary contract tests for registered FastAPI routes (Tabbit zero-test remediation)."""

from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import server

_PATH_PARAM_DEFAULTS = {
    "device_id": "dev-contract",
    "session_id": "sess-contract",
    "task_id": "task-contract",
    "audio_id": "audio-contract.wav",
    "member_id": "mem-contract",
    "binding_id": "bind-contract",
    "name": "backend-contract",
    "rule_id": "rule-contract",
    "key_id": "key-contract",
    "family": "default",
    "account_id": "acct-contract",
    "job_id": "job-contract",
}


def _fill_path(path: str) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return _PATH_PARAM_DEFAULTS.get(key, f"test-{key}")

    return re.sub(r"\{(\w+)\}", repl, path)


def _api_routes() -> list[APIRoute]:
    return [route for route in server.app.routes if isinstance(route, APIRoute)]


def _route(method: str, path: str) -> APIRoute | None:
    for route in _api_routes():
        if route.path == path and method in route.methods:
            return route
    return None


@pytest.fixture
def api_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-contract-token")
    monkeypatch.delenv("LIMA_ALLOW_ANONYMOUS", raising=False)
    monkeypatch.delenv("LIMA_PUBLIC_DEMO_ENABLED", raising=False)
    monkeypatch.delenv("LIMA_RUNTIME_ENV", raising=False)
    return TestClient(server.app, raise_server_exceptions=False)


# Static/asset routes may legitimately 404 when the backing file is absent.
_SMOKE_SKIP_PREFIXES = (
    "/uploads/",
    "/digital-human/",
)
_SMOKE_SKIP_EXACT = {"/", "/admin", "/sw.js", "/manifest.json"}


def _api_routes_for_smoke() -> list[tuple[str, str]]:
    probes: list[tuple[str, str]] = []
    for route in _api_routes():
        if route.path in _SMOKE_SKIP_EXACT:
            continue
        if any(route.path.startswith(prefix) for prefix in _SMOKE_SKIP_PREFIXES):
            continue
        method = next(iter(sorted(route.methods - {"HEAD", "OPTIONS"})))
        probes.append((method, route.path))
    return probes


# --- Public health (no API key) ---

PUBLIC_GET_OK = [
    "/health",
    "/device/v1/health",
]


@pytest.mark.parametrize("path", PUBLIC_GET_OK)
def test_public_health_routes_return_ok(api_client, path):
    response = api_client.get(path)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:200]}"
    body = response.json()
    assert body.get("status") in {"ok", "degraded", None} or "anonymous_access" in body.get("security", {})


# --- Private OpenAI-compatible API (LIMA_API_KEY) ---

PRIVATE_POST_UNAUTH = [
    "/v1/chat/completions",
    "/v1/embeddings",
    "/v1/images/generations",
]

PRIVATE_GET_UNAUTH = [
    "/v1/models",
    "/v1/status",
    "/v1/ops/metrics/prometheus",
    "/v1/ops/summary",
]


@pytest.mark.parametrize("path", PRIVATE_POST_UNAUTH)
def test_private_post_routes_reject_missing_api_key(api_client, path):
    response = api_client.post(path, json={})
    assert response.status_code == 401, f"{path} should require API key, got {response.status_code}"


@pytest.mark.parametrize("path", PRIVATE_GET_UNAUTH)
def test_private_get_routes_reject_missing_api_key(api_client, path):
    response = api_client.get(path)
    assert response.status_code == 401, f"{path} should require API key, got {response.status_code}"


def test_private_routes_accept_configured_api_key(api_client, monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "contract-test-key")
    headers = {"Authorization": "Bearer contract-test-key"}

    models = api_client.get("/v1/models", headers=headers)
    assert models.status_code == 200
    assert isinstance(models.json().get("data"), list)

    summary = api_client.get("/v1/ops/summary", headers=headers)
    assert summary.status_code == 200
    assert "status" in summary.json() or "backends" in summary.json()


# --- Device app native API (JWT) ---

DEVICE_APP_GET_UNAUTH = [
    "/device/v1/app/devices",
    "/device/v1/app/devices/dev-contract/chat-sessions",
    "/device/v1/app/devices/dev-contract/chat-history",
    "/device/v1/app/tasks?device_id=dev-contract",
]


@pytest.mark.parametrize("path", DEVICE_APP_GET_UNAUTH)
def test_device_app_routes_reject_missing_jwt(api_client, path):
    filled = _fill_path(path.split("?", 1)[0])
    query = ""
    if "?" in path:
        _, query = path.split("?", 1)
    url = f"{filled}?{query}" if query else filled
    response = api_client.get(url)
    assert response.status_code == 401, f"{url} should require JWT, got {response.status_code}"


# --- Admin API ---

ADMIN_GET_UNAUTH = [
    "/admin/api/stats",
    "/admin/api/backends",
    "/admin/api/logs",
    "/admin/api/devices",
]


@pytest.mark.parametrize("path", ADMIN_GET_UNAUTH)
def test_admin_api_routes_reject_missing_session(api_client, path):
    response = api_client.get(path)
    assert response.status_code in {401, 403}, f"{path} -> {response.status_code}"


# --- Upload / demo / ws ticket ---


def test_upload_post_requires_jwt(api_client):
    response = api_client.post("/upload", files={"file": ("x.png", b"data", "image/png")})
    assert response.status_code == 401


def test_public_demo_fails_closed_when_disabled(api_client):
    response = api_client.post(
        "/public/demo/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 503


def test_ws_ticket_post_requires_api_key(api_client):
    response = api_client.post("/v1/ws/ticket", json={})
    assert response.status_code == 401


# --- Registry smoke: every route is reachable (not 404) with minimal probe ---


def _minimal_body(method: str, path: str) -> dict[str, Any] | None:
    if method in {"POST", "PUT", "PATCH"}:
        if "chat" in path or "completions" in path:
            return {"model": "lima-1.3", "messages": [{"role": "user", "content": "hi"}]}
        if "login" in path or "register" in path:
            return {"phone": "13000000000", "code": "000000"}
        return {}
    return None


@pytest.mark.parametrize(
    "method,path",
    _api_routes_for_smoke(),
)
def test_registered_route_not_404(api_client, method, path):
    """Smoke: wrong auth or bad body must not look like an unregistered route."""
    filled = _fill_path(path)
    body = _minimal_body(method, filled)
    if method == "GET":
        response = api_client.get(filled)
    elif method == "DELETE":
        response = api_client.delete(filled)
    elif method == "PUT":
        response = api_client.put(filled, json=body or {})
    elif method == "PATCH":
        response = api_client.patch(filled, json=body or {})
    else:
        response = api_client.post(filled, json=body if body is not None else {})

    assert response.status_code != 404, f"{method} {filled} returned 404 — route missing from registry?"


def test_server_registers_minimum_route_surface():
    paths = {route.path for route in _api_routes()}
    required = {
        "/health",
        "/v1/chat/completions",
        "/v1/models",
        "/device/v1/health",
        "/device/v1/app/devices",
        "/public/demo/chat",
        "/upload",
        "/v1/ws/ticket",
    }
    missing = required - paths
    assert not missing, f"missing core routes: {sorted(missing)}"
    assert len(paths) >= 120, f"expected broad route surface, got {len(paths)}"
