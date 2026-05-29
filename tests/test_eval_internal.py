"""Tests for /internal/v1/eval/call (P2-25)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def eval_client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "eval-test-key")
    from routes.eval_internal import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_eval_internal_requires_auth(eval_client):
    resp = eval_client.post(
        "/internal/v1/eval/call",
        json={
            "backend": "scnet_qwen30b",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 401


def test_eval_internal_direct_call(eval_client, monkeypatch):
    import backends

    monkeypatch.setattr(
        "http_caller.call_api",
        lambda backend, messages, max_tokens: "def foo(): pass",
    )
    if "scnet_qwen30b" not in backends.BACKENDS:
        monkeypatch.setitem(
            backends.BACKENDS,
            "scnet_qwen30b",
            {"key": "x", "url": "http://example", "model": "m", "fmt": "openai"},
        )
    resp = eval_client.post(
        "/internal/v1/eval/call",
        json={
            "backend": "scnet_qwen30b",
            "messages": [{"role": "user", "content": "write foo"}],
            "max_tokens": 128,
        },
        headers={"Authorization": "Bearer eval-test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "def foo" in data["answer"]
