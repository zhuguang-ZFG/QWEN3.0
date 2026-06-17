"""System and metadata endpoints for the LiMa API."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from access_guard import require_private_api_key
from backends_registry import BACKENDS
import health_state
import health_tracker
import server_lifespan

router = APIRouter()

_model_id = "lima-1.3"
_model_created = int(time.time())
_loaded_modules: dict[str, Any] = {}
_PUBLIC_MODEL_NAME = os.environ.get("PUBLIC_MODEL_NAME", "LiMa")


def _circuit_breaker_status() -> dict:
    """Return breaker summary compatible with the legacy circuit-breaker shape."""
    result = {}
    for name in BACKENDS:
        quality = health_state.get_backend_quality(name)
        total = quality["total_requests"]
        errors = quality["empty_count"] + quality["error_msg_count"]
        error_rate = f"{errors / total:.1%}" if total > 0 else "0.0%"
        result[name] = {
            "state": "open" if health_tracker.is_cooled_down(name) else "closed",
            "failures": health_state.get_backend_state(name).get("state", "ok") != "ok",
            "error_rate": error_rate,
            "avg_latency_ms": int(health_state.get_latency_map().get(name, 0)),
            "total_calls": total,
        }
    return result


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
    phases = list(server_lifespan.STARTUP_PHASES)
    has_error = any(p.get("status") == "error" for p in phases)
    startup_status = "error" if has_error else ("ready" if phases else "starting")
    return {
        "status": "ok" if startup_status != "error" else "degraded",
        "version": "2.0",
        "model": _model_id,
        "modules": _loaded_modules,
        "startup": {"status": startup_status, "phases": phases},
    }


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
        "detail": ("Provider credentials are not exposed via this API; use a server-side Gemini Live proxy."),
    }


@router.get("/v1/status", dependencies=[Depends(require_private_api_key)])
async def router_status():
    return {
        "circuit_breakers": _circuit_breaker_status(),
        "backends": list(BACKENDS.keys()),
        "route_table": {},
        "public_model": _PUBLIC_MODEL_NAME,
    }
