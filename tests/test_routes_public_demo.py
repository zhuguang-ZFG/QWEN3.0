"""Tests for routes/public_demo.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import public_demo


@pytest.fixture(autouse=True)
def _reset_deps_and_rate_hits(monkeypatch):
    public_demo._deps.clear()
    public_demo._public_demo_hits.clear()
    # ensure demo disabled by default unless test enables it
    monkeypatch.delenv("LIMA_PUBLIC_DEMO_ENABLED", raising=False)
    monkeypatch.delenv("LIMA_PUBLIC_DEMO_MAX_PER_MINUTE", raising=False)
    yield
    public_demo._deps.clear()
    public_demo._public_demo_hits.clear()


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(public_demo.router)
    return TestClient(app)


@pytest.fixture
def enabled_client(client, monkeypatch):
    monkeypatch.setenv("LIMA_PUBLIC_DEMO_ENABLED", "true")
    public_demo._deps["model_id"] = "lima-test"
    public_demo._deps["handle_chat"] = MagicMock(return_value={"answer": "hi"})
    return client


def test_disabled_returns_503(client):
    response = client.post("/public/demo/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_missing_messages(enabled_client):
    response = enabled_client.post("/public/demo/chat", json={})
    assert response.status_code == 400
    assert "messages" in response.json()["detail"]


def test_unsupported_tools(enabled_client):
    response = enabled_client.post(
        "/public/demo/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "tools": [{"type": "function"}]},
    )
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_unsupported_stream(enabled_client):
    response = enabled_client.post(
        "/public/demo/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert response.status_code == 400


def test_message_too_long(enabled_client):
    long_text = "a" * (public_demo._PUBLIC_DEMO_MAX_CHARS + 1)
    response = enabled_client.post(
        "/public/demo/chat",
        json={"messages": [{"role": "user", "content": long_text}]},
    )
    assert response.status_code == 400
    assert "too long" in response.json()["detail"]


def test_rate_limit_per_client_ip(enabled_client, monkeypatch):
    monkeypatch.setenv("LIMA_PUBLIC_DEMO_MAX_PER_MINUTE", "2")
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert enabled_client.post("/public/demo/chat", json=body).status_code == 200
    assert enabled_client.post("/public/demo/chat", json=body).status_code == 200
    response = enabled_client.post("/public/demo/chat", json=body)
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_successful_chat_uses_handle_chat(enabled_client):
    body = {"messages": [{"role": "user", "content": "hello"}]}
    response = enabled_client.post("/public/demo/chat", json=body)
    assert response.status_code == 200
    assert response.json() == {"answer": "hi"}
    handle = public_demo._deps["handle_chat"]
    assert handle.called
    call_args = handle.call_args
    chat_req = call_args.args[0]
    assert chat_req.model == "lima-test"
    assert chat_req.stream is False
    assert chat_req.max_tokens == public_demo._PUBLIC_DEMO_MAX_TOKENS
    kwargs = call_args.kwargs
    assert kwargs["fmt"] == "openai"
    assert kwargs["ide_source"] == "public_demo"


def test_max_tokens_clamped(enabled_client):
    body = {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 9999}
    response = enabled_client.post("/public/demo/chat", json=body)
    assert response.status_code == 200
    chat_req = public_demo._deps["handle_chat"].call_args.args[0]
    assert chat_req.max_tokens == public_demo._PUBLIC_DEMO_MAX_TOKENS


def test_temperature_passed_through(enabled_client):
    body = {"messages": [{"role": "user", "content": "hello"}], "temperature": 0.3}
    response = enabled_client.post("/public/demo/chat", json=body)
    assert response.status_code == 200
    chat_req = public_demo._deps["handle_chat"].call_args.args[0]
    assert chat_req.temperature == 0.3


def test_invalid_max_tokens_falls_back(enabled_client):
    body = {"messages": [{"role": "user", "content": "hello"}], "max_tokens": "bad"}
    response = enabled_client.post("/public/demo/chat", json=body)
    assert response.status_code == 200
    chat_req = public_demo._deps["handle_chat"].call_args.args[0]
    assert chat_req.max_tokens == public_demo._PUBLIC_DEMO_MAX_TOKENS
