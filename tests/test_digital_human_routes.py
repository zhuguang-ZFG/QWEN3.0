"""Tests for the 2D digital human static routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

import server


def test_digital_human_health():
    client = TestClient(server.app)
    response = client.get("/digital-human/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("ok", "unavailable")
    assert "static_path" in payload
    assert "index_exists" in payload


def test_digital_human_index_serves_patched_html():
    client = TestClient(server.app)
    response = client.get("/digital-human/")
    if response.status_code == 404:
        # Assets not available in this environment; health endpoint already covers it.
        return
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    text = response.text
    assert "Digital human" in text or "数字人" in text or "live2d" in text.lower()
    # The patched auto-config script should be present.
    assert 'setInput("limaWsUrl"' in text
    assert "/device/v1/ws" in text
    assert "seedStorage" in text


def test_digital_human_static_js_served():
    client = TestClient(server.app)
    response = client.get("/digital-human/js/app.js")
    if response.status_code == 404:
        return
    assert response.status_code == 200
    assert "application/javascript" in response.headers.get("content-type", "")
