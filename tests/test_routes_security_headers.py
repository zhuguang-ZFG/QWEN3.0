"""Tests for routes/security_headers.py middleware.

AUDIT fix: the four edge headers (X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, HSTS) are only set by the middleware when LIMA_BEHIND_NGINX
is not "1" (i.e. local dev / Docker direct). In production behind nginx, nginx
sets them and the middleware skips them to avoid duplicates. CSP,
Permissions-Policy, and X-XSS-Protection are always set by the middleware.
"""

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

    def test_always_on_headers_present(self):
        """CSP, Permissions-Policy, X-XSS-Protection are always set."""
        response = self._client().get("/")
        assert response.status_code == 200
        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
        assert "Content-Security-Policy" in response.headers
        assert "X-XSS-Protection" in response.headers

    def test_edge_headers_absent_behind_nginx(self, monkeypatch):
        """Behind nginx (default), edge headers are NOT set by middleware."""
        monkeypatch.setenv("LIMA_BEHIND_NGINX", "1")
        response = self._client().get("/")
        assert "X-Frame-Options" not in response.headers
        assert "X-Content-Type-Options" not in response.headers
        assert "Referrer-Policy" not in response.headers
        assert "Strict-Transport-Security" not in response.headers

    def test_edge_headers_present_without_nginx(self, monkeypatch):
        """Without nginx (LIMA_BEHIND_NGINX=0), edge headers ARE set by middleware."""
        monkeypatch.setenv("LIMA_BEHIND_NGINX", "0")
        response = self._client().get("/")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Strict-Transport-Security" not in response.headers  # http, no HSTS

    def test_hsts_on_https_without_nginx(self, monkeypatch):
        """HSTS set on https when not behind nginx."""
        monkeypatch.setenv("LIMA_BEHIND_NGINX", "0")
        response = self._client().get("/", headers={"X-Forwarded-Proto": "https"})
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    def test_csp_is_strict(self):
        """CSP must enforce default-src 'self' and frame-ancestors 'none'."""
        response = self._client().get("/")
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
