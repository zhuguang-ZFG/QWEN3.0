"""Regression tests for routes/admin_extra_config.py URL validation (P0-3)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def admin_config_client(monkeypatch):
    """Provide a TestClient for the config import endpoint with admin auth satisfied."""
    # Satisfy verify_admin without requiring a real LIMA_ADMIN_TOKEN env var.
    monkeypatch.setattr("routes.admin_auth.get_admin_token", lambda: "test-admin-token")

    import backends_registry

    # Use an isolated registry so tests do not mutate the global BACKENDS dict.
    monkeypatch.setattr(backends_registry, "BACKENDS", {})

    from routes.admin_extra_config import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client


ADMIN_AUTH = {"Authorization": "Bearer test-admin-token"}


def _import_payload(url: str) -> dict:
    return {
        "version": "1.0",
        "backends": {
            "test-backend": {"url": url, "model": "m", "fmt": "openai"},
        },
    }


def test_config_import_rejects_http(admin_config_client):
    resp = admin_config_client.post(
        "/api/config/import",
        headers=ADMIN_AUTH,
        json=_import_payload("http://example.com/v1"),
    )
    assert resp.status_code == 400
    assert "unsafe" in resp.text.lower()


def test_config_import_rejects_loopback(admin_config_client):
    resp = admin_config_client.post(
        "/api/config/import",
        headers=ADMIN_AUTH,
        json=_import_payload("https://127.0.0.1:8080/v1"),
    )
    assert resp.status_code == 400


def test_config_import_rejects_private_ip(admin_config_client):
    resp = admin_config_client.post(
        "/api/config/import",
        headers=ADMIN_AUTH,
        json=_import_payload("https://192.168.1.1/v1"),
    )
    assert resp.status_code == 400


def test_config_import_accepts_public_https(admin_config_client):
    resp = admin_config_client.post(
        "/api/config/import",
        headers=ADMIN_AUTH,
        json=_import_payload("https://1.1.1.1/v1"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "test-backend" in data["imported"]
