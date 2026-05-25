"""Request body size limit middleware (ASGI receive cap)."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from http_body_limit import (
    BodySizeLimitMiddleware,
    enforce_request_body_limit,
    install_body_size_limit,
)
from server_bootstrap import MAX_BODY_SIZE


@pytest.mark.asyncio
async def test_install_body_size_limit_stops_over_cap():
    chunks = [b"a" * 1024] * 3
    idx = 0

    async def receive():
        nonlocal idx
        if idx < len(chunks):
            body = chunks[idx]
            idx += 1
            return {"type": "http.request", "body": body, "more_body": idx < len(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [(b"content-type", b"application/json")],
    }
    request = Request(scope, receive)
    limited, state = install_body_size_limit(request, max_size=1500)

    total = 0
    while True:
        message = await limited.receive()
        if message["type"] == "http.disconnect":
            break
        if message["type"] == "http.request":
            total += len(message.get("body", b"") or b"")
            if not message.get("more_body", False):
                break

    assert state["too_large"] is True
    assert total <= 1500


def test_rejects_declared_oversized_content_length():
    app = FastAPI()

    @app.middleware("http")
    async def _limit(request: Request, call_next):
        return await enforce_request_body_limit(request, call_next, max_size=MAX_BODY_SIZE)

    @app.post("/v1/chat/completions")
    async def _chat():
        return {"ok": True}

    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        headers={
            "Content-Length": str(MAX_BODY_SIZE + 1),
            "Content-Type": "application/json",
        },
        content=b"{}",
    )
    assert response.status_code == 413


def test_require_content_length_for_json_api_without_header():
    from http_body_limit import _require_content_length_for_json

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/messages",
        "headers": [(b"content-type", b"application/json")],
    }
    request = Request(scope, receive=lambda: {"type": "http.request", "body": b"", "more_body": False})
    response = _require_content_length_for_json(request)
    assert response is not None
    assert response.status_code == 400
    assert "Content-Length required" in response.body.decode()


def test_chunked_body_over_limit_returns_413_without_full_body():
    seen: dict[str, int] = {}
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=15)

    @app.post("/v1/messages")
    async def _messages(request: Request):
        body = await request.body()
        seen["len"] = len(body)
        return {"len": len(body)}

    payload = b'{"messages":[]}' + b"x" * 20

    def _chunks():
        yield payload[:12]
        yield payload[12:]

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/messages",
        headers={
            "Content-Type": "application/json",
            "Transfer-Encoding": "chunked",
        },
        content=_chunks(),
    )
    assert response.status_code == 413
    assert seen.get("len", 0) < len(payload)


def test_allows_chunked_json_without_content_length_header():
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_size=MAX_BODY_SIZE)

    @app.post("/v1/messages")
    async def _messages(request: Request):
        await request.json()
        return {"ok": True}

    client = TestClient(app)
    response = client.post(
        "/v1/messages",
        headers={
            "Content-Type": "application/json",
            "Transfer-Encoding": "chunked",
        },
        content=b'{"messages":[]}',
    )
    assert response.status_code == 200
