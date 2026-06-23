"""Tests for routes/security_headers.py middleware."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from routes.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware:
    def _client(self) -> TestClient:
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/")
        def index():
            return PlainTextResponse("ok")

        return TestClient(app)

    def test_baseline_headers_on_http(self):
        response = self._client().get("/")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
        assert "Content-Security-Policy" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_on_https_scheme(self):
        response = self._client().get("/", headers={"X-Forwarded-Proto": "https"})
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
