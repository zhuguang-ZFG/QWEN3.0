"""Disabled SCNet reverse sidecar placeholder.

Runs an OpenAI-compatible shell on 127.0.0.1:4505, but returns 503 until the
real SCNet web/API adapter is implemented and evaluated.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from reverse_gateway.providers.scnet import forward_chat, sidecar_health

app = FastAPI(title="LiMa SCNet Reverse Sidecar", version="0.1")


@app.get("/health")
def health() -> dict[str, object]:
    return sidecar_health()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    status_code, payload = forward_chat(body)
    return JSONResponse(status_code=status_code, content=payload)
