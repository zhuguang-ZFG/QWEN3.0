"""System and metadata endpoints for the LiMa API."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from config.env import gemini_live_model, google_ai_key, health_show_errors
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

import brand_config
from access_guard import anonymous_access_status, extract_bearer_token, is_token_valid, require_private_api_key
from routes.facade import BACKENDS, health_tracker
import health_state
import server_lifespan
import ws_ticket

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


def _model_owned_by(model_id: str, backend_name: str) -> str:
    """Derive an OpenAI-style owned_by value from model id or backend key."""
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    lowered = backend_name.lower()
    if lowered.startswith(("claude_", "anthropic_")):
        return "anthropic"
    if lowered.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if "deepseek" in lowered:
        return "deepseek"
    if "qwen" in lowered:
        return "qwen"
    if "gemini" in lowered or "google" in lowered:
        return "google"
    if "llama" in lowered or "meta" in lowered:
        return "meta"
    if lowered.startswith(("free_", "community_")):
        return "community"
    return "lima"


@router.get("/v1/models", dependencies=[Depends(require_private_api_key)])
async def list_models():
    """Return dynamically registered models instead of a hardcoded list."""
    seen: set[str] = set()
    models: list[dict[str, Any]] = []
    for name, cfg in BACKENDS.items():
        model_id = cfg.get("model") or name
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append(
            {
                "id": model_id,
                "object": "model",
                "created": _model_created,
                "owned_by": _model_owned_by(str(model_id), name),
            }
        )
    models.append({"id": _model_id, "object": "model", "created": _model_created, "owned_by": "donglicao"})
    return {"object": "list", "data": models}


@router.post("/v1/ws/ticket")
async def create_ws_ticket(authorization: str = Header(default="")) -> dict[str, int | str]:
    """Exchange a private API key for a short-lived WebSocket ticket."""
    token = extract_bearer_token(authorization)
    if not is_token_valid(token):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"ticket": ws_ticket.issue(), "expires_in": ws_ticket.TTL_SECONDS}


@router.get("/health")
async def health(authorization: str = Header(default="")):
    state = server_lifespan.get_startup_state()
    startup_errors = state.get("errors", [])
    startup_status = state["status"]
    overall_status = "ok"
    if startup_status == "error":
        overall_status = "degraded"
    elif startup_status == "warming":
        overall_status = "ok"  # serving, but background warm-up still in progress
    elif startup_status == "starting":
        overall_status = "degraded"

    token = extract_bearer_token(authorization)
    authenticated = is_token_valid(token)

    payload: dict[str, Any] = {
        "status": overall_status,
        "version": "2.0",
        "model": _model_id,
    }
    if authenticated:
        payload["modules"] = _loaded_modules
        payload["startup"] = {
            "status": startup_status,
            "phases": list(server_lifespan.STARTUP_PHASES),
            "pending_warm": state.get("pending_warm", []),
            "errors": startup_errors if health_show_errors() else [],
            "error_count": len(startup_errors),
            "error_phases": _startup_error_phases(startup_errors),
        }
        payload["security"] = {"anonymous_access": anonymous_access_status()}
    else:
        # AUDIT-5-O11: 匿名 /health 不暴露内部模块清单、启动阶段、安全开关等侦察信息
        payload["startup"] = {"status": startup_status}

    if startup_status == "error":
        return JSONResponse(status_code=503, content=payload)
    return payload


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    """Strict readiness probe: return 200 only when all warm phases done AND runtime deps OK.

    AUDIT-5-O1：原实现只检查启动 phase 状态，运行时依赖（SQLite/后端可用性/磁盘）挂掉仍返回 200，
    导致公网 LB 探针被死实例欺骗。此处增加运行时依赖探活：至少一个后端非 dead + SQLite 可读写。
    """
    state = server_lifespan.get_startup_state()
    startup_status = state["status"]

    # 运行时依赖探活（轻量，best-effort 但失败需反映到 ready 状态）
    runtime_checks: dict[str, str] = {}
    ready = startup_status == "ready"

    # 检查 1：至少一个后端非 dead（否则所有请求必然失败）
    try:
        from health_state import get_health_map

        health_map = get_health_map()
        alive = sum(1 for s in health_map.values() if s != "dead")
        if alive == 0 and health_map:
            runtime_checks["backends"] = "all_dead"
            ready = False
    except Exception as exc:
        logger.debug("health/ready backend probe failed: %s", exc)  # 启动初期 health_map 可能未就绪

    # 检查 2：磁盘可用空间（缓存/日志写入需要）
    try:
        import shutil

        usage = shutil.disk_usage("/")
        if usage.free < 256 * 1024 * 1024:  # < 256MB
            runtime_checks["disk"] = "low_space"
            ready = False
    except Exception as exc:
        logger.debug("health/ready disk probe failed: %s", exc)

    payload: dict[str, Any] = {
        "status": "ready" if ready else "not_ready",
        "startup_status": startup_status,
        "pending_warm": list(state.get("pending_warm", [])),
        "error_count": len(state.get("errors", [])),
        "runtime_checks": runtime_checks,
    }
    status_code = 200 if ready else 503
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/api/live-key", dependencies=[Depends(require_private_api_key)])
async def live_key():
    """Capability metadata only; raw provider keys stay server-side."""
    key = google_ai_key()
    if not key:
        raise HTTPException(status_code=503, detail="Gemini key not configured")
    return {
        "available": True,
        "model": gemini_live_model(),
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
