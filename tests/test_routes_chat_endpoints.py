"""Tests for routes/chat_endpoints.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import chat_endpoints


@pytest.fixture(autouse=True)
def _reset_deps():
    chat_endpoints._deps.clear()
    yield
    chat_endpoints._deps.clear()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(chat_endpoints.router)
    return TestClient(app)


@pytest.fixture
def deps_client(client):
    chat_endpoints._deps.update(
        {
            "model_id": "lima-test",
            "handle_chat": MagicMock(return_value={"answer": "ok"}),
            "vision_route": MagicMock(return_value={"answer": "vision-ok", "backend": "vision-backend"}),
            "stream_vision_response": MagicMock(return_value=["data: {}\n\n"]),
            "record_request": MagicMock(),
            "client_ip": MagicMock(return_value="127.0.0.1"),
            "detect_ide": MagicMock(return_value=""),
        }
    )
    return client


def test_missing_auth_header(client):
    response = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 401


def test_invalid_json_body(deps_client):
    response = deps_client.post("/v1/chat/completions", data="not json", headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 400


def test_missing_messages_returns_400(deps_client):
    response = deps_client.post("/v1/chat/completions", json={}, headers={"Authorization": "Bearer test-key"})
    assert response.status_code == 400
    assert "messages" in response.json()["error"]["message"]


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=False)
def test_rate_limit_returns_429(mock_check, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 429
    assert "rate limit" in response.json()["error"]["message"].lower()


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=True)
@patch("routes.chat_endpoints.detect_vision_request", return_value=True)
def test_vision_shortcut_non_stream(mock_vision, mock_rate, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "look"}]},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "vision-ok"
    assert data["x_lima_meta"]["backend"] == "vision-backend"


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=True)
@patch("routes.chat_endpoints.detect_vision_request", return_value=True)
def test_vision_shortcut_stream(mock_vision, mock_rate, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "look"}], "stream": True},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=True)
@patch("routes.chat_endpoints.detect_vision_request", return_value=False)
def test_handle_chat_success(mock_vision, mock_rate, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"model": "lima-test", "messages": [{"role": "user", "content": "hello"}]},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"answer": "ok"}
    handle_chat = chat_endpoints._deps["handle_chat"]
    assert handle_chat.called
    call_args = handle_chat.call_args
    chat_req = call_args.args[0]
    assert chat_req.model == "lima-test"
    assert chat_req.messages[0].content == "hello"
    kwargs = call_args.kwargs
    assert kwargs["fmt"] == "openai"
    assert kwargs["client_ip"] == "127.0.0.1"


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=True)
@patch("routes.chat_endpoints.detect_vision_request", return_value=False)
def test_thinking_flag_passthrough(mock_vision, mock_rate, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "thinking": True},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    chat_req = chat_endpoints._deps["handle_chat"].call_args.args[0]
    assert chat_req.thinking is True


@patch("routes.chat_endpoints.rate_limiter.check_rate_limit", return_value=True)
@patch("routes.chat_endpoints.detect_vision_request", return_value=False)
def test_tools_routed_to_handle_chat(mock_vision, mock_rate, deps_client):
    response = deps_client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}], "tools": [{"type": "function"}]},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    chat_req = chat_endpoints._deps["handle_chat"].call_args.args[0]
    assert chat_req.has_tools is True
