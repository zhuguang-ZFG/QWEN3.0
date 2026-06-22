"""System and metadata endpoints for the LiMa API."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

import brand_config
from access_guard import anonymous_access_status, extract_bearer_token, is_token_valid, require_private_api_key
from backends_registry import BACKENDS
import health_state
import health_tracker
import server_lifespan
import ws_ticket

_SHOW_HEALTH_ERRORS = os.environ.get("LIMA_HEALTH_SHOW_ERRORS", "0").strip().lower() in {"1", "true", "yes"}

router = APIRouter()

from lima_constants import MODEL_ID

_model_id = MODEL_ID
_model_created = int(time.time())
_loaded_modules: dict[str, Any] = {}
_PUBLIC_MODEL_NAME = brand_config.PUBLIC_MODEL_NAME


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


def _startup_error_phases(errors: list[Any]) -> list[str]:
    phases: list[str] = []
    for error in errors:
        phase = str(error.get("phase", "unknown")) if isinstance(error, dict) else "unknown"
        if phase not in phases:
            phases.append(phase)
    return phases


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


@router.post("/v1/ws/ticket")
async def create_ws_ticket(authorization: str = Header(default="")) -> dict[str, int | str]:
    """Exchange a private API key for a short-lived WebSocket ticket."""
    token = extract_bearer_token(authorization)
    if not is_token_valid(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"ticket": ws_ticket.issue(), "expires_in": ws_ticket.TTL_SECONDS}


@router.get("/health")
async def health():
    state = server_lifespan.get_startup_state()
    phases = list(server_lifespan.STARTUP_PHASES)
    startup_errors = state.get("errors", [])
    startup_status = state["status"]
    overall_status = "ok"
    if startup_status == "error":
        overall_status = "degraded"
    elif startup_status == "warming":
        overall_status = "ok"  # serving, but background warm-up still in progress
    elif startup_status == "starting":
        overall_status = "degraded"
    payload = {
        "status": overall_status,
        "version": "2.0",
        "model": _model_id,
        "modules": _loaded_modules,
        "startup": {
            "status": startup_status,
            "phases": phases,
            "pending_warm": state.get("pending_warm", []),
            "errors": startup_errors if _SHOW_HEALTH_ERRORS else [],
            "error_count": len(startup_errors),
            "error_phases": _startup_error_phases(startup_errors),
        },
        "security": {
            "anonymous_access": anonymous_access_status(),
        },
    }
    if startup_status == "error":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/api/live-key", dependencies=[Depends(require_private_api_key)])
async def live_key():
    """Capability metadata only; raw provider keys stay server-side."""
    key = os.environ.get("GOOGLE_AI_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {
        "available": True,
        "model": os.environ.get(
            "LIMA_GEMINI_LIVE_MODEL",
            "models/gemini-3.1-flash-live-preview",
        ),
        "url": "/v1/live",
        "auth": "server_side_only",
        "detail": ("Connect to the LiMa Gemini Live WebSocket proxy at /v1/live."),
    }


@router.get("/v1/status", dependencies=[Depends(require_private_api_key)])
async def router_status():
    return {
        "circuit_breakers": _circuit_breaker_status(),
        "backends": list(BACKENDS.keys()),
        "route_table": {},
        "public_model": _PUBLIC_MODEL_NAME,
    }
