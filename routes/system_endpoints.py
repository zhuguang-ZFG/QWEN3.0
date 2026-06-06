"""System and metadata endpoints for the LiMa API."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

_log = logging.getLogger(__name__)

import routing_facade
from access_guard import require_private_api_key

router = APIRouter()

_model_id = "lima-1.3"
_model_created = int(time.time())
_loaded_modules: dict[str, Any] = {}


def inject_state(*, model_id: str, model_created: int, loaded_modules: dict[str, Any]) -> None:
    global _model_id, _model_created, _loaded_modules
    _model_id = model_id
    _model_created = model_created
    _loaded_modules = loaded_modules


@router.get("/v1")
async def openai_v1_info():
    """OpenAI-compatible /v1 info — helps IDE clients discover the API."""
    return {
        "object": "list",
        "description": "LiMa OpenAI-compatible API",
        "endpoints": ["/v1/chat/completions", "/v1/responses", "/v1/models"],
    }


@router.get("/v1/models", dependencies=[Depends(require_private_api_key)])
async def list_models(request: Request):
    models = [
        {"id": "claude-opus-4-7", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "claude-sonnet-4", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "claude-haiku-4", "object": "model", "created": _model_created, "owned_by": "anthropic"},
        {"id": "gpt-5.4", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "gpt-4.1", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "gpt-5", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "o1", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "o4-mini", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "o3-mini", "object": "model", "created": _model_created, "owned_by": "openai"},
        {"id": "deepseek-v4-pro", "object": "model", "created": _model_created, "owned_by": "deepseek"},
        {"id": "deepseek-v4-flash", "object": "model", "created": _model_created, "owned_by": "deepseek"},
        {"id": "deepseek-r1", "object": "model", "created": _model_created, "owned_by": "deepseek"},
        {"id": "qwen3-coder", "object": "model", "created": _model_created, "owned_by": "qwen"},
        {"id": "qwen3-235b", "object": "model", "created": _model_created, "owned_by": "qwen"},
        {"id": "gemini-2.0-flash", "object": "model", "created": _model_created, "owned_by": "google"},
        {"id": "gemini-2.5-pro", "object": "model", "created": _model_created, "owned_by": "google"},
        {"id": "llama-3.3-70b", "object": "model", "created": _model_created, "owned_by": "meta"},
        {"id": "mistral-large", "object": "model", "created": _model_created, "owned_by": "mistral"},
        {"id": "codestral", "object": "model", "created": _model_created, "owned_by": "mistral"},
        {"id": "mimo-v2.5-pro", "object": "model", "created": _model_created, "owned_by": "mimo"},
        {"id": _model_id, "object": "model", "created": _model_created, "owned_by": "donglicao"},
    ]

    # ── Protocol adapter: add maxOutputTokens for OpenCode compatibility ──
    try:
        from opencode_protocol_adapter import build_model_output_limits
        models = build_model_output_limits(models)
    except Exception as exc:
        _log.debug("system_endpoints: protocol adapter output limits failed", exc_info=True)

    # OpenCode curated model list: return a focused subset of coding-capable models.
    # Default enabled for OpenCode clients; set LIMA_OPENCODE_MODEL_LIST=0 to disable.
    ua = request.headers.get("user-agent", "").lower()
    if ("opencode" in ua or "opencode-ai" in ua) and os.environ.get("LIMA_OPENCODE_MODEL_LIST", "1") != "0":
        # Curated coding-agent models: models with strong tool-calling + coding ability
        opencode_models = [
            {"id": "claude-sonnet-4", "object": "model", "created": _model_created, "owned_by": "anthropic"},
            {"id": "claude-opus-4-7", "object": "model", "created": _model_created, "owned_by": "anthropic"},
            {"id": "gpt-5.4", "object": "model", "created": _model_created, "owned_by": "openai"},
            {"id": "gpt-4.1", "object": "model", "created": _model_created, "owned_by": "openai"},
            {"id": "gpt-5", "object": "model", "created": _model_created, "owned_by": "openai"},
            {"id": "o4-mini", "object": "model", "created": _model_created, "owned_by": "openai"},
            {"id": "deepseek-v4-pro", "object": "model", "created": _model_created, "owned_by": "deepseek"},
            {"id": "deepseek-r1", "object": "model", "created": _model_created, "owned_by": "deepseek"},
            {"id": "qwen3-coder", "object": "model", "created": _model_created, "owned_by": "qwen"},
            {"id": "codestral", "object": "model", "created": _model_created, "owned_by": "mistral"},
            {"id": "mimo-v2.5-pro", "object": "model", "created": _model_created, "owned_by": "mimo"},
            {"id": _model_id, "object": "model", "created": _model_created, "owned_by": "donglicao"},
        ]
        return {"object": "list", "data": opencode_models}

    return {"object": "list", "data": models}


@router.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "model": _model_id, "modules": _loaded_modules}


@router.get("/api/live-key", dependencies=[Depends(require_private_api_key)])
async def live_key():
    """Capability metadata only; raw provider keys stay server-side."""
    key = os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {
        "available": True,
        "model": "models/gemini-2.0-flash-live-001",
        "auth": "server_side_only",
        "detail": (
            "Provider credentials are not exposed via this API; "
            "use a server-side Gemini Live proxy."
        ),
    }


@router.get("/v1/status", dependencies=[Depends(require_private_api_key)])
async def router_status():
    return routing_facade.router_status_payload()
