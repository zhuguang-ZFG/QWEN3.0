"""Integration tests for POST /v1/responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import server


def test_responses_endpoint_non_stream(monkeypatch):
    async def fake_handle_chat(req, **kwargs):
        return JSONResponse({
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "lima-1.3",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "PONG"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    resp = client.post(
        "/v1/responses",
        headers={
            "Authorization": "Bearer test-key",
            "User-Agent": "OpenCode/1.0",
        },
        json={
            "model": "lima-1.3",
            "input": "ping",
            "instructions": "You are OpenCode.",
            "stream": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "response"
    assert data["status"] == "completed"
    assert data["output"][0]["content"][0]["text"] == "PONG"


def test_responses_endpoint_stream(monkeypatch):
    from fastapi.responses import StreamingResponse

    async def gen():
        yield 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
        yield "data: [DONE]\n\n"

    async def fake_handle_chat(req, **kwargs):
        return StreamingResponse(gen(), media_type="text/event-stream")

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    with client.stream(
        "POST",
        "/v1/responses",
        headers={"Authorization": "Bearer test-key", "User-Agent": "OpenCode/1.0"},
        json={"model": "lima-1.3", "input": "hi", "stream": True},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "response.created" in body
    assert "response.output_text.delta" in body
    assert "response.completed" in body
