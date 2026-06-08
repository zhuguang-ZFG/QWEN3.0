"""Integration tests for POST /v1/responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import server


def test_responses_endpoint_non_stream(monkeypatch):
    async def fake_handle_chat(req, **kwargs):
        assert req.temperature == 0.2
        assert req.top_p == 0.7
        assert (
            kwargs["request_headers"]["x-session-affinity"]
            == "session-recorded-opencode-loop"
        )
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
            "temperature": 0.2,
            "top_p": 0.7,
            "store": False,
            "prompt_cache_key": "session-recorded-opencode-loop",
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "medium", "summary": "auto"},
            "text": {"verbosity": "low"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "response"
    assert data["status"] == "completed"
    assert data["output"][0]["content"][0]["text"] == "PONG"
    assert data["store"] is False
    assert data["prompt_cache_key"] == "session-recorded-opencode-loop"
    assert data["include"] == ["reasoning.encrypted_content"]
    assert data["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert data["text"] == {"verbosity": "low"}


def test_responses_endpoint_session_affinity_header_wins(monkeypatch):
    async def fake_handle_chat(req, **kwargs):
        assert kwargs["request_headers"]["x-session-affinity"] == "explicit-affinity"
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
        })

    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setattr(server, "_handle_chat", fake_handle_chat)

    client = TestClient(server.app)
    resp = client.post(
        "/v1/responses",
        headers={
            "Authorization": "Bearer test-key",
            "User-Agent": "OpenCode/1.0",
            "x-session-affinity": "explicit-affinity",
        },
        json={
            "model": "lima-1.3",
            "input": "ping",
            "stream": False,
            "prompt_cache_key": "body-affinity",
        },
    )

    assert resp.status_code == 200


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
        json={
            "model": "lima-1.3",
            "input": "hi",
            "stream": True,
            "store": False,
            "prompt_cache_key": "session-recorded-opencode-loop",
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"effort": "medium", "summary": "auto"},
            "text": {"verbosity": "low"},
        },
    ) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "response.created" in body
    assert "response.output_text.delta" in body
    assert "response.completed" in body
    assert '"prompt_cache_key": "session-recorded-opencode-loop"' in body
    assert '"include": ["reasoning.encrypted_content"]' in body
    assert '"text": {"verbosity": "low"}' in body
