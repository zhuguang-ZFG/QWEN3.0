"""Verify BodySizeLimitMiddleware rejects chunked streaming bodies that exceed max_bytes."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from dlc_api.middleware import BodySizeLimitMiddleware


def _make_app(max_bytes: int = 100) -> FastAPI:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)

    @app.post("/upload")
    async def upload(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse({"size": len(body)})

    return app


def test_chunked_body_over_limit_returns_413() -> None:
    """Streaming body without Content-Length that exceeds max_bytes → 413."""
    client = TestClient(_make_app(max_bytes=50))
    # Send 80 bytes without Content-Length header (chunked transfer)
    resp = client.post(
        "/upload",
        content=b"x" * 80,
        headers={"transfer-encoding": "chunked"},
    )
    assert resp.status_code == 413
    assert resp.json()["error"] == "request_entity_too_large"


def test_content_length_over_limit_returns_413() -> None:
    """Declared Content-Length > max_bytes → 413 without reading body."""
    client = TestClient(_make_app(max_bytes=50))
    resp = client.post(
        "/upload",
        content=b"x" * 80,
    )
    assert resp.status_code == 413


def test_normal_request_within_limit_succeeds() -> None:
    """Body within limit passes through normally."""
    client = TestClient(_make_app(max_bytes=200))
    payload = b"hello world"
    resp = client.post("/upload", content=payload)
    assert resp.status_code == 200
    assert resp.json()["size"] == len(payload)


def test_streaming_body_within_limit_succeeds() -> None:
    """Chunked body within limit passes through normally."""
    client = TestClient(_make_app(max_bytes=200))
    resp = client.post(
        "/upload",
        content=b"small",
        headers={"transfer-encoding": "chunked"},
    )
    assert resp.status_code == 200
