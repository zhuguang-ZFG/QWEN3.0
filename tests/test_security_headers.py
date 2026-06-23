"""Tests for routes/security_headers.py — security headers middleware."""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from routes.security_headers import SecurityHeadersMiddleware


app = Starlette()
app.add_middleware(SecurityHeadersMiddleware)


@app.route("/")
def homepage(_):
    return PlainTextResponse("ok")


class TestSecurityHeadersMiddleware:
    def test_basic_headers(self):
        client = TestClient(app)
        response = client.get("/")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers

    def test_hsts_on_https(self):
        client = TestClient(app)
        response = client.get("/", headers={"X-Forwarded-Proto": "https"})
        assert "Strict-Transport-Security" in response.headers

    def test_no_hsts_on_http(self):
        client = TestClient(app)
        response = client.get("/")
        assert "Strict-Transport-Security" not in response.headers
