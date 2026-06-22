"""Tests for global HTTP security headers middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient

import server


def test_security_headers_present_on_health() -> None:
    client = TestClient(server.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-XSS-Protection") == "0"
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_added_for_https_requests() -> None:
    client = TestClient(server.app, base_url="https://testserver")
    response = client.get("/health")
    assert response.status_code == 200
    assert "max-age=31536000" in response.headers.get("Strict-Transport-Security", "")
