"""Tests for CORS middleware configured in server.py."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import server


class TestServerCors:
    @pytest.fixture(autouse=True)
    def _client(self):
        self.client = TestClient(server.app)

    def test_health_get_includes_cors_headers(self):
        response = self.client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
        assert "X-LiMa-Trace-Id" in response.headers.get("access-control-expose-headers", "")

    def test_health_preflight_returns_200(self):
        response = self.client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
        assert "authorization" in (response.headers.get("access-control-allow-headers", "").lower())

    def test_chat_completions_preflight_returns_200(self):
        response = self.client.options(
            "/v1/chat/completions",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Authorization",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
