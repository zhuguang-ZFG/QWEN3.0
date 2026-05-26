import asyncio

import server
import routes.anthropic_stream as anthropic_stream
import routes.anthropic_stream_branches as anthropic_stream_branches


def _chat_request(query: str) -> server.ChatRequest:
    return server.ChatRequest(
        model="test-model",
        messages=[server.Message(role="user", content=query)],
        stream=True,
        max_tokens=64,
    )


async def _collect_anthropic_stream(req: server.ChatRequest) -> str:
    chunks = []
    async for chunk in server._anthropic_stream(req, "test-model"):
        chunks.append(chunk)
    return "".join(chunks)


def test_anthropic_speculative_stream_hides_backend_footer(monkeypatch):
    monkeypatch.setattr(server.smart_router, "detect_image_intent", lambda _query: (False, ""))
    monkeypatch.setattr(
        server.smart_router,
        "analyze",
        lambda *_args, **_kwargs: {"intent": "chat", "complexity": 0.1},
    )
    monkeypatch.setattr(anthropic_stream_branches, "needs_orchestration", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(anthropic_stream, "_record_request", lambda *_args, **_kwargs: None)

    async def fake_stream(_query, _messages, _max_tokens, _ide_source):
        yield "internal_speculative_backend", "public stream text"

    monkeypatch.setattr(anthropic_stream_branches, "speculative_stream_chunks", fake_stream)

    body = asyncio.run(_collect_anthropic_stream(_chat_request("hello")))

    assert "public stream text" in body
    assert "[LiMa" not in body
    assert "internal_speculative_backend" not in body


def test_anthropic_fake_stream_hides_backend_footer(monkeypatch):
    monkeypatch.setattr(server.smart_router, "detect_image_intent", lambda _query: (False, ""))
    monkeypatch.setattr(
        server.smart_router,
        "analyze",
        lambda *_args, **_kwargs: {"intent": "chat", "complexity": 0.1},
    )
    monkeypatch.setattr(anthropic_stream_branches, "needs_orchestration", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        anthropic_stream_branches,
        "orchestrate",
        lambda _query: {
            "answer": "This public answer is long enough to pass the quality gate.",
            "backend": "internal_fake_backend",
        },
    )
    monkeypatch.setattr(anthropic_stream_branches, "quality_check", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(anthropic_stream, "_record_request", lambda *_args, **_kwargs: None)

    body = asyncio.run(_collect_anthropic_stream(_chat_request("plan this task")))

    assert "This public answer" in body
    assert "long enough" in body
    assert "[LiMa" not in body
    assert "internal_fake_backend" not in body
