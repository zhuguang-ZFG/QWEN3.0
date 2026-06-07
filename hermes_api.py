"""hermes_api.py — Hermes Agent HTTP API microservice.

OpenAI-compatible FastAPI service that bridges LiMa ↔ Hermes Agent.
Listens on 127.0.0.1:8699, registers as LiMa backend on port 8699.

Endpoints:
  POST /v1/chat/completions  — OpenAI-compatible chat (streaming + non-streaming)
  GET  /health                — Health check
  GET  /v1/models             — List models

Usage:
  python hermes_api.py                        # default port 8699
  HERMES_API_PORT=8700 python hermes_api.py   # custom port
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, AsyncGenerator

# Ensure local modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from hermes_bridge import call_lima, LIMA_MODEL, LIMA_TIMEOUT

logger = logging.getLogger("hermes_api")
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("HERMES_DEBUG") == "1" else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

HERMES_API_PORT = int(os.environ.get("HERMES_API_PORT", "8699"))
MODEL_ID = os.environ.get("HERMES_MODEL_ID", "hermes-agent")
MODEL_CREATED = int(os.environ.get("HERMES_MODEL_CREATED", "1720000000"))

app = FastAPI(
    title="Hermes Agent API",
    version="0.1.0",
    description="LiMa ↔ Hermes Agent bridge — OpenAI-compatible microservice",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ── Health ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_ID, "port": HERMES_API_PORT}


# ── Models ──────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": MODEL_CREATED,
                "owned_by": "hermes-agent",
            }
        ],
    }


# ── Chat Completions ────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint.

    Accepts standard OpenAI chat completion JSON body.
    Supports both streaming (stream=True) and non-streaming modes.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")

    model = body.get("model", LIMA_MODEL)
    max_tokens = body.get("max_tokens", 4096)
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)
    timeout = body.get("timeout", LIMA_TIMEOUT)

    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    t0 = time.time()

    if stream:
        return StreamingResponse(
            _stream_response(messages, model, max_tokens, temperature, timeout, chat_id, t0),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming
    try:
        response_text, latency_ms = call_lima(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as e:
        logger.exception("hermes_api: chat completion failed")
        raise HTTPException(status_code=502, detail=f"Hermes Agent call failed: {e}")

    finish_time = time.time()
    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": int(finish_time),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


async def _stream_response(
    messages: list[dict],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    chat_id: str,
    t0: float,
) -> AsyncGenerator[str, None]:
    """Generate SSE streaming response chunks."""
    try:
        response_text, latency_ms = call_lima(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
    except Exception as e:
        logger.exception("hermes_api: stream call failed")
        error_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": f"[ERROR: {e}]"},
                    "finish_reason": "error",
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Simulate streaming: split response into chunks
    chunk_size = max(1, len(response_text) // 20) if len(response_text) > 20 else len(response_text)
    for i in range(0, len(response_text), chunk_size):
        chunk_text = response_text[i : i + chunk_size]
        chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        # Small delay for natural streaming feel
        await _async_sleep(0.01)

    # Final chunk with finish_reason
    final_chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


async def _async_sleep(seconds: float) -> None:
    """Async sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)


# ── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting Hermes Agent API on 127.0.0.1:%d (model=%s)", HERMES_API_PORT, MODEL_ID)
    uvicorn.run(
        "hermes_api:app",
        host="127.0.0.1",
        port=HERMES_API_PORT,
        log_level="info",
        access_log=os.environ.get("HERMES_ACCESS_LOG", "0") == "1",
    )
