"""Tests for the admin probe ingress endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.probe_state import reset_probe_state
from routes import admin_probe_ingress
from routes.admin_auth import verify_admin


@pytest.fixture(autouse=True)
def _reset_probe_state() -> None:
    reset_probe_state()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_probe_ingress.router)
    return app


def _build_client(override_admin: bool = False) -> TestClient:
    """Return a TestClient, optionally overriding admin auth for GET endpoints."""
    app = _build_app()
    if override_admin:
        app.dependency_overrides[verify_admin] = lambda: None
    return TestClient(app)


def test_probe_ingress_disabled_returns_503(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "0")
    client = _build_client()
    response = client.post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer any-token"},
        json={"source": "jdcloud", "probes": []},
    )
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_probe_ingress_invalid_token_returns_401(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    client = _build_client()
    response = client.post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer wrong-token"},
        json={"source": "jdcloud", "probes": []},
    )
    assert response.status_code == 401


def test_probe_ingress_valid_token_and_get_query(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")

    payload = {
        "source": "jdcloud",
        "probes": [
            {
                "provider": "groq",
                "status": "alive",
                "latency_ms": 120.0,
                "price_tier": "low",
                "checked_at": "2026-06-28T12:00:00Z",
            }
        ],
    }
    post_response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json=payload,
    )
    assert post_response.status_code == 200
    assert post_response.json() == {"recorded": 1}

    get_response = _build_client(override_admin=True).get("/admin/api/probe/jdcloud")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["count"] == 1
    assert body["probes"][0]["provider"] == "groq"
    assert body["probes"][0]["status"] == "alive"
    assert body["probes"][0]["price_tier"] == "low"


def test_probe_ingress_sanitizes_sensitive_metadata(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")

    payload = {
        "source": "jdcloud",
        "probes": [
            {
                "provider": "groq",
                "status": "alive",
                "latency_ms": 120.0,
                "metadata": {
                    "region": "cn-north-1",
                    "api_key": "should-be-removed",
                    "nested": {"auth_token": "also-removed", "keep": "value"},
                },
            }
        ],
    }
    post_response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json=payload,
    )
    assert post_response.status_code == 200
    assert post_response.json() == {"recorded": 1}

    body = _build_client(override_admin=True).get("/admin/api/probe/jdcloud").json()
    metadata = body["probes"][0]["metadata"]
    assert metadata["region"] == "cn-north-1"
    assert "api_key" not in metadata
    assert "auth_token" not in metadata.get("nested", {})
    assert metadata["nested"]["keep"] == "value"


def test_probe_ingress_aggregates_multiple_providers(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")

    payload = {
        "source": "jdcloud",
        "probes": [
            {"provider": "groq", "status": "alive", "latency_ms": 120.0},
            {"provider": "openrouter", "status": "degraded", "latency_ms": 250.0},
        ],
    }
    post_response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json=payload,
    )
    assert post_response.status_code == 200
    assert post_response.json() == {"recorded": 2}

    body = _build_client(override_admin=True).get("/admin/api/probe/jdcloud").json()
    assert body["count"] == 2
    providers = {probe["provider"] for probe in body["probes"]}
    assert providers == {"groq", "openrouter"}


def test_probe_ingress_empty_probes_list(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json={"source": "jdcloud", "probes": []},
    )
    assert response.status_code == 200
    assert response.json() == {"recorded": 0}


@pytest.mark.parametrize(
    "payload",
    [
        {"probes": []},
        {"source": "", "probes": []},
        {"source": 123, "probes": []},
    ],
)
def test_probe_ingress_missing_or_invalid_source_returns_400(monkeypatch, payload):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json=payload,
    )
    assert response.status_code == 400
    assert "source" in response.json()["detail"].lower()


def test_probe_ingress_probes_not_a_list_returns_400(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json={"source": "jdcloud", "probes": {"provider": "groq"}},
    )
    assert response.status_code == 400
    assert "list" in response.json()["detail"].lower()


def test_probe_ingress_skips_non_dict_and_missing_provider(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json={
            "source": "jdcloud",
            "probes": [
                "not-a-dict",
                {"status": "alive", "latency_ms": 120.0},
                {"provider": "groq", "status": "alive", "latency_ms": 120.0},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"recorded": 1}

    body = _build_client(override_admin=True).get("/admin/api/probe/jdcloud").json()
    assert body["count"] == 1
    assert body["probes"][0]["provider"] == "groq"


def test_probe_ingress_skips_invalid_latency_type(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    response = _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json={
            "source": "jdcloud",
            "probes": [{"provider": "groq", "status": "alive", "latency_ms": "fast"}],
        },
    )
    assert response.status_code == 200
    assert response.json() == {"recorded": 0}


def test_probe_jdcloud_get_requires_admin_auth(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    monkeypatch.setenv("LIMA_ADMIN_TOKEN", "admin-token")
    response = _build_client(override_admin=False).get("/admin/api/probe/jdcloud")
    assert response.status_code in (401, 403)


def test_probe_jdcloud_get_filters_by_source(monkeypatch):
    monkeypatch.setenv("LIMA_PROBE_INGRESS_ENABLED", "1")
    monkeypatch.setenv("LIMA_PROBE_INGRESS_TOKEN", "probe-token")
    _build_client().post(
        "/admin/api/probe/ingress",
        headers={"Authorization": "Bearer probe-token"},
        json={
            "source": "other-source",
            "probes": [{"provider": "groq", "status": "alive", "latency_ms": 120.0}],
        },
    )
    response = _build_client(override_admin=True).get("/admin/api/probe/jdcloud")
    assert response.status_code == 200
    assert response.json() == {"probes": [], "count": 0}
