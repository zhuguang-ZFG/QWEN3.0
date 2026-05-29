"""Central FastAPI router registration (CQ-014 slice 3)."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI


@dataclass
class RouteRegistryDeps:
    """Dependencies required to wire routers onto the app."""

    model_id: str
    model_created: int
    stats: dict
    stats_lock: threading.Lock
    backend_enabled: dict
    loaded_modules: dict
    client_ip: Callable[..., str]
    detect_ide: Callable[..., str]
    elapsed_ms: Callable[..., int]
    vision_route: Callable[..., Any]
    stream_vision_response: Callable[..., Any]
    record_request: Callable[..., None]
    anthropic_native_stream: Callable[..., Any]
    anthropic_native_forward: Callable[..., Any]
    anthropic_stream: Callable[..., Any]
    anthropic_stream_passthrough: Callable[..., Any]
    handle_chat: Callable[..., Any]


@dataclass
class RegisteredRoutes:
    """Handler aliases re-exported by server.py for compatibility."""

    chat_completions: Callable[..., Any]
    anthropic_messages: Callable[..., Any]
    list_models: Callable[..., Any]
    health: Callable[..., Any]
    live_key: Callable[..., Any]
    router_status: Callable[..., Any]


def register_all_routes(app: FastAPI, deps: RouteRegistryDeps) -> RegisteredRoutes:
    """Mount all LiMa routers and inject shared state."""
    from routes.images import router as images_router, build_pollinations_url
    import routes.images as images_mod

    images_mod.inject_record_request(deps.record_request)
    app.include_router(images_router)
    _ = build_pollinations_url  # imported for server-side image intent handling

    from routes.chat_endpoints import router as chat_endpoints_router
    import routes.chat_endpoints as chat_endpoints_mod

    chat_endpoints_mod.inject_deps(
        model_id=deps.model_id,
        client_ip=deps.client_ip,
        detect_ide=deps.detect_ide,
        elapsed_ms=deps.elapsed_ms,
        vision_route=deps.vision_route,
        stream_vision_response=deps.stream_vision_response,
        record_request=deps.record_request,
        anthropic_native_stream=deps.anthropic_native_stream,
        anthropic_native_forward=deps.anthropic_native_forward,
        anthropic_stream=deps.anthropic_stream,
        anthropic_stream_passthrough=deps.anthropic_stream_passthrough,
        handle_chat=deps.handle_chat,
    )
    app.include_router(chat_endpoints_router)

    from routes.embeddings import router as embeddings_router

    app.include_router(embeddings_router)

    from routes.admin import router as admin_router
    from routes.admin_agent_audit import router as admin_agent_audit_router
    import routes.admin as admin_mod

    admin_mod.inject_state(deps.stats, deps.stats_lock, deps.backend_enabled)
    app.include_router(admin_router)
    app.include_router(admin_agent_audit_router)

    import routes.quality_gate as quality_gate_mod

    quality_gate_mod.inject_state(deps.backend_enabled)

    from routes.system_endpoints import router as system_endpoints_router
    import routes.system_endpoints as system_endpoints_mod

    system_endpoints_mod.inject_state(
        model_id=deps.model_id,
        model_created=deps.model_created,
        loaded_modules=deps.loaded_modules,
    )
    app.include_router(system_endpoints_router)

    from routes.device_gateway import router as device_gateway_router

    app.include_router(device_gateway_router)
    deps.loaded_modules["device_gateway"] = True

    try:
        from routes.ops_metrics import router as ops_metrics_router

        app.include_router(ops_metrics_router)
        deps.loaded_modules["ops_metrics"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] ops_metrics module not loaded: %s", exc)
        deps.loaded_modules["ops_metrics"] = False

    try:
        from routes.health_dashboard import router as health_dashboard_router

        app.include_router(health_dashboard_router)
    except ImportError as exc:
        logging.warning("[STARTUP] health_dashboard module not loaded: %s", exc)

    try:
        from lima_mcp.server import router as mcp_router

        app.include_router(mcp_router)
        deps.loaded_modules["mcp"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] MCP module not loaded: %s", exc)
        deps.loaded_modules["mcp"] = False

    try:
        from routes.agent_tasks import router as agent_tasks_router

        app.include_router(agent_tasks_router)
        deps.loaded_modules["agent_tasks"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] agent_tasks module not loaded: %s", exc)
        deps.loaded_modules["agent_tasks"] = False

    try:
        from routes.agent_execute import router as agent_execute_router
        import routes.agent_execute as agent_execute_mod

        agent_execute_mod.inject_state(admin_token=os.environ.get("LIMA_API_KEY", ""))
        app.include_router(agent_execute_router)
        deps.loaded_modules["agent_execute"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] agent_execute module not loaded: %s", exc)
        deps.loaded_modules["agent_execute"] = False

    try:
        from routes.fleet_api import router as fleet_router
        import routes.fleet_api as fleet_mod

        fleet_mod.inject_state(admin_token=os.environ.get("LIMA_API_KEY", ""))
        app.include_router(fleet_router)
        deps.loaded_modules["fleet"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] fleet module not loaded: %s", exc)
        deps.loaded_modules["fleet"] = False

    try:
        from routes.eval_internal import router as eval_internal_router

        app.include_router(eval_internal_router)
        deps.loaded_modules["eval_internal"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] eval_internal module not loaded: %s", exc)
        deps.loaded_modules["eval_internal"] = False

    try:
        from routes.outcome_ingest import router as outcome_router

        app.include_router(outcome_router)
        deps.loaded_modules["outcome_ingest"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] outcome_ingest not loaded: %s", exc)
        deps.loaded_modules["outcome_ingest"] = False

    try:
        from routes.telegram import router as telegram_router

        app.include_router(telegram_router)
        deps.loaded_modules["telegram"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] telegram module not loaded: %s", exc)
        deps.loaded_modules["telegram"] = False

    try:
        from routes.github_webhook import router as github_webhook_router

        app.include_router(github_webhook_router)
        deps.loaded_modules["github_webhook"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] github_webhook module not loaded: %s", exc)
        deps.loaded_modules["github_webhook"] = False

    try:
        from routes.gitee_webhook import router as gitee_webhook_router

        app.include_router(gitee_webhook_router)
        deps.loaded_modules["gitee_webhook"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] gitee_webhook module not loaded: %s", exc)
        deps.loaded_modules["gitee_webhook"] = False

    try:
        from routes.channel_gateway import router as channel_gateway_router

        app.include_router(channel_gateway_router)
        deps.loaded_modules["channel_gateway"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] channel_gateway module not loaded: %s", exc)
        deps.loaded_modules["channel_gateway"] = False

    return RegisteredRoutes(
        chat_completions=chat_endpoints_mod.chat_completions,
        anthropic_messages=chat_endpoints_mod.anthropic_messages,
        list_models=system_endpoints_mod.list_models,
        health=system_endpoints_mod.health,
        live_key=system_endpoints_mod.live_key,
        router_status=system_endpoints_mod.router_status,
    )
