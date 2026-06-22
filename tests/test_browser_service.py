"""Tests for the provider probe browser microservice."""

from fastapi.testclient import TestClient
import pytest

from provider_probe import browser_service
from provider_probe import browser_lifecycle

pytestmark = pytest.mark.offline_probe


def test_browser_launch_options_include_configured_executable(monkeypatch):
    monkeypatch.setenv("PROBE_CHROMIUM_EXECUTABLE", "/usr/bin/google-chrome")

    options = browser_lifecycle._browser_launch_options()

    assert options["executable_path"] == "/usr/bin/google-chrome"
    assert options["headless"] is True
    assert "--no-sandbox" in options["args"]


def test_ready_reports_browser_launch_failure(monkeypatch):
    async def fail_browser():
        raise RuntimeError("Executable doesn't exist at /root/.cache/ms-playwright/chromium")

    # Monkeypatch the local reference in browser_service, not the source module.
    monkeypatch.setattr(browser_service, "_get_browser", fail_browser)

    response = TestClient(browser_service.app).get("/ready")

    assert response.status_code == 503
    data = response.json()["detail"]
    text = str(data)
    assert data["ready"] is False
    assert data["service"] == "probe-browser"
    assert data["error_class"] == "RuntimeError"
    assert "/root/.cache" not in text


def test_ready_reports_browser_available(monkeypatch):
    async def browser_ok():
        return object()

    monkeypatch.setattr(browser_service, "_get_browser", browser_ok)

    response = TestClient(browser_service.app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"ready": True, "service": "probe-browser"}


def test_render_launch_failure_returns_json_error(monkeypatch):
    async def fail_browser():
        raise RuntimeError("Executable doesn't exist at /root/.cache/ms-playwright/chromium")

    monkeypatch.setattr(browser_service, "_get_browser", fail_browser)

    response = TestClient(browser_service.app).post(
        "/render",
        json={"url": "https://example.com", "wait_ms": 1},
    )

    assert response.status_code == 503
    data = response.json()["detail"]
    assert data["error_class"] == "RuntimeError"
    assert data["phase"] == "browser_launch"
    assert "/root/.cache" not in str(data)
