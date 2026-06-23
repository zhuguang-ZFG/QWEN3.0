"""Tests for routes/eval_internal.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import eval_internal as ev


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ev.router)
    return TestClient(app)


def _auth_header():
    return {"Authorization": "Bearer test-key"}


@patch.object(ev, "BACKENDS", {"test-backend": {"key": "secret"}})
@patch.object(ev, "call_pinned_backend")
def test_successful_eval_call(mock_call, client):
    mock_call.return_value = ("test-backend", "hello")
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "test-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["backend"] == "test-backend"
    assert payload["answer"] == "hello"


def test_unknown_backend_returns_404(client):
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "missing", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 404
    assert "unknown backend" in response.json()["detail"]


@patch.object(ev, "BACKENDS", {"no-key-backend": {"key": ""}})
def test_backend_without_key_returns_404(client):
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "no-key-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 404
    assert "not configured" in response.json()["detail"]


@patch.object(ev, "BACKENDS", {"test-backend": {"key": "secret"}})
@patch.object(ev, "call_pinned_backend", side_effect=RuntimeError("boom"))
def test_call_exception_returns_502(mock_call, client):
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "test-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 502
    assert "RuntimeError" in response.json()["detail"]


@patch.object(ev, "BACKENDS", {"test-backend": {"key": "secret"}})
@patch.object(ev, "call_pinned_backend", return_value=("exhausted", ""))
def test_exhausted_backend_returns_502(mock_call, client):
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "test-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 502
    assert "exhausted" in response.json()["detail"]


@patch.object(ev, "BACKENDS", {"test-backend": {"key": "secret"}})
@patch.object(ev, "call_pinned_backend", return_value=("test-backend", "   "))
def test_empty_answer_returns_502(mock_call, client):
    response = client.post(
        "/internal/v1/eval/call",
        headers=_auth_header(),
        json={"backend": "test-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 502
    assert "exhausted" in response.json()["detail"]


def test_missing_auth_returns_401(client):
    response = client.post(
        "/internal/v1/eval/call",
        json={"backend": "test-backend", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 401
