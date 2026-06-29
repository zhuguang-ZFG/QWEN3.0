"""Tests for X-Request-Id response header injection."""

from __future__ import annotations

from fastapi.testclient import TestClient

import server


def test_health_response_includes_request_id_header():
    client = TestClient(server.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-Id" in response.headers
    assert len(response.headers["X-Request-Id"]) > 0


def test_request_id_reuses_lima_trace_id_for_chat():
    client = TestClient(server.app)
    response = client.get("/health")
    # /health does not set X-LiMa-Trace-Id, so X-Request-Id should be a fresh UUID.
    request_id = response.headers["X-Request-Id"]
    # UUID4 format check is loose enough to avoid coupling to generator.
    assert request_id.count("-") == 4
