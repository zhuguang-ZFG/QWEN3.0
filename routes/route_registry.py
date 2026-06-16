"""Central FastAPI router registration (CQ-014 slice 3)."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI

from channel_retirement import mark_retired_modules


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
    handle_chat: Callable[..., Any]


@dataclass
class RegisteredRoutes:
    """Handler aliases re-exported by server.py for compatibility."""

    chat_completions: Callable[..., Any]
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
        handle_chat=deps.handle_chat,
    )
    app.include_router(chat_endpoints_router)

    from routes.public_demo import router as public_demo_router
    import routes.public_demo as public_demo_mod

    public_demo_mod.inject_deps(
        model_id=deps.model_id,
        handle_chat=deps.handle_chat,
    )
    app.include_router(public_demo_router)

    from routes.embeddings import router as embeddings_router

    app.include_router(embeddings_router)

    from routes.admin import router as admin_router
    # NOTE: admin_agent_audit deleted in strategic pivot (2026-06-09)
    import routes.admin as admin_mod

    admin_mod.inject_state(deps.stats, deps.stats_lock, deps.backend_enabled)
    app.include_router(admin_router)

    from routes.static_files import router as static_files_router

    app.include_router(static_files_router)

    # NOTE: quality_gate.py deleted in strategic pivot (2026-06-09)
    # quality_gate_direct.py and quality_gate_tiers.py remain as utilities

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
        from routes.xiaozhi_v1_compat import router as xiaozhi_v1_compat_router

        app.include_router(xiaozhi_v1_compat_router)
        deps.loaded_modules["xiaozhi_v1_compat"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] xiaozhi_v1_compat module not loaded: %s", exc)
        deps.loaded_modules["xiaozhi_v1_compat"] = False

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
        from routes.token_sync import router as token_sync_router

        app.include_router(token_sync_router)
        deps.loaded_modules["token_sync"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] token_sync not loaded: %s", exc)
        deps.loaded_modules["token_sync"] = False

    mark_retired_modules(deps.loaded_modules)

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
        from routes.device_memory import router as device_memory_router

        app.include_router(device_memory_router)
        deps.loaded_modules["device_memory"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] device_memory module not loaded: %s", exc)
        deps.loaded_modules["device_memory"] = False

    try:
        from routes.device_support import router as device_support_router

        app.include_router(device_support_router)
        deps.loaded_modules["device_support"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] device_support module not loaded: %s", exc)
        deps.loaded_modules["device_support"] = False

    try:
        from routes.device_ota import router as device_ota_router

        app.include_router(device_ota_router)
        deps.loaded_modules["device_ota"] = True
    except ImportError as exc:
        logging.warning("[STARTUP] device_ota module not loaded: %s", exc)
        deps.loaded_modules["device_ota"] = False

    return RegisteredRoutes(
        chat_completions=chat_endpoints_mod.chat_completions,
        list_models=system_endpoints_mod.list_models,
        health=system_endpoints_mod.health,
        live_key=system_endpoints_mod.live_key,
        router_status=system_endpoints_mod.router_status,
    )
