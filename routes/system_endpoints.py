"""System and metadata endpoints for the LiMa API."""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from access_guard import require_private_api_key
import smart_router

router = APIRouter()

_model_id = "lima-1.3"
_model_created = int(time.time())
_loaded_modules: dict[str, Any] = {}


def inject_state(*, model_id: str, model_created: int, loaded_modules: dict[str, Any]) -> None:
    global _model_id, _model_created, _loaded_modules
    _model_id = model_id
    _model_created = model_created
    _loaded_modules = loaded_modules


@router.get("/v1/models", dependencies=[Depends(require_private_api_key)])
async def list_models():
    models = [
        {"id": "claude-opus-4-7", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "claude-sonnet-4", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "claude-haiku-4", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "gpt-5.4", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "gpt-4.1", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "o1", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "o4-mini", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "deepseek-v4-pro", "object": "model", "created": _model_created, "owned_by": "deepseek"},
        {"id": "deepseek-v4-flash", "object": "model", "created": _model_created, "owned_by": "deepseek"},
        {"id": "qwen3-coder", "object": "model", "created": _model_created, "owned_by": "qwen"},
        {"id": "gemini-2.0-flash", "object": "model", "created": _model_created, "owned_by": "google"},
        {"id": "llama-3.3-70b", "object": "model", "created": _model_created, "owned_by": "meta"},
        {"id": _model_id, "object": "model", "created": _model_created, "owned_by": "donglicao"},
    ]
    return {"object": "list", "data": models}


@router.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "model": _model_id, "modules": _loaded_modules}


@router.get("/api/live-key", dependencies=[Depends(require_private_api_key)])
async def live_key():
    key = os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {"key": key, "model": "models/gemini-2.0-flash-live-001"}


@router.get("/v1/status", dependencies=[Depends(require_private_api_key)])
async def router_status():
    return {
        "circuit_breakers": smart_router.cb_status(),
        "backends": list(smart_router.BACKENDS.keys()),
        "route_table": smart_router.ROUTE,
        "public_model": smart_router.PUBLIC_MODEL_NAME,
    }
