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


def _try_include(
    app: FastAPI,
    loaded: dict,
    import_path: str,
    module_key: str,
    *,
    inject: Callable[[Any], None] | None = None,
) -> bool:
    """Import a router module and include it on *app*.

    Records success/failure in *loaded* under *module_key*.
    Returns True when the router was mounted.
    """
    try:
        import importlib

        mod = importlib.import_module(import_path)
        app.include_router(mod.router)  # type: ignore[attr-defined]
        if inject is not None:
            inject(mod)
        loaded[module_key] = True
        return True
    except ImportError as exc:
        logging.warning("[STARTUP] %s module not loaded: %s", module_key, exc)
        loaded[module_key] = False
        return False


def _register_core_routes(app: FastAPI, deps: RouteRegistryDeps) -> tuple:
    """Mount always-present routers and return handler aliases."""
    from routes.images import router as images_router, build_pollinations_url
    import routes.images as images_mod

    images_mod.inject_record_request(deps.record_request)
    app.include_router(images_router)
    _ = build_pollinations_url

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

    public_demo_mod.inject_deps(model_id=deps.model_id, handle_chat=deps.handle_chat)
    app.include_router(public_demo_router)

    from routes.embeddings import router as embeddings_router

    app.include_router(embeddings_router)

    from routes.admin import router as admin_router
    import routes.admin as admin_mod

    admin_mod.inject_state(deps.stats, deps.stats_lock, deps.backend_enabled)
    app.include_router(admin_router)

    from routes.static_files import router as static_files_router

    app.include_router(static_files_router)

    from routes.digital_human import mount_static_files, router as digital_human_router

    app.include_router(digital_human_router)
    mount_static_files(app)

    from routes.system_endpoints import router as system_endpoints_router
    import routes.system_endpoints as system_endpoints_mod

    system_endpoints_mod.inject_state(
        model_id=deps.model_id,
        model_created=deps.model_created,
        loaded_modules=deps.loaded_modules,
    )
    app.include_router(system_endpoints_router)

    from routes.device_gateway import router as device_gateway_router
    from routes.device_app_api import router as device_app_router
    from routes.device_app_members import router as device_app_members_router
    from routes.device_app_misc import router as device_app_misc_router

    app.include_router(device_gateway_router)
    app.include_router(device_app_router)
    app.include_router(device_app_members_router)
    app.include_router(device_app_misc_router)
    deps.loaded_modules["device_gateway"] = True
    deps.loaded_modules["device_app_api"] = True
    deps.loaded_modules["device_app_members"] = True
    deps.loaded_modules["device_app_misc"] = True

    from routes.gemini_live_proxy import router as gemini_live_router

    app.include_router(gemini_live_router)
    deps.loaded_modules["gemini_live_proxy"] = True

    return chat_endpoints_mod, system_endpoints_mod


def _register_optional_routes(app: FastAPI, deps: RouteRegistryDeps) -> None:
    """Mount optional routers with graceful ImportError fallback."""
    loaded = deps.loaded_modules
    if os.environ.get("LIMA_XIAOZHI_COMPAT_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        _try_include(app, loaded, "routes.xiaozhi_v1_compat", "xiaozhi_v1_compat")
    else:
        loaded["xiaozhi_v1_compat"] = False
    _try_include(app, loaded, "routes.ops_metrics", "ops_metrics")
    _try_include(app, loaded, "routes.health_dashboard", "health_dashboard")

    def _fleet_inject(mod: Any) -> None:
        mod.inject_state(admin_token=os.environ.get("LIMA_API_KEY", ""))

    _try_include(app, loaded, "routes.fleet_api", "fleet", inject=_fleet_inject)
    _try_include(app, loaded, "routes.eval_internal", "eval_internal")
    _try_include(app, loaded, "routes.outcome_ingest", "outcome_ingest")
    _try_include(app, loaded, "routes.token_sync", "token_sync")
    _try_include(app, loaded, "routes.device_memory", "device_memory")
    _try_include(app, loaded, "routes.device_support", "device_support")
    _try_include(app, loaded, "routes.device_ota", "device_ota")

    # Retired subsystems — see docs/CODEBASE_COLD_PRUNE_PRIORITY_CN.md P5.
    loaded["mcp"] = False
    loaded["github_webhook"] = False
    loaded["gitee_webhook"] = False


def register_all_routes(app: FastAPI, deps: RouteRegistryDeps) -> RegisteredRoutes:
    """Mount all LiMa routers and inject shared state."""
    chat_endpoints_mod, system_endpoints_mod = _register_core_routes(app, deps)
    _register_optional_routes(app, deps)

    mark_retired_modules(deps.loaded_modules)

    return RegisteredRoutes(
        chat_completions=chat_endpoints_mod.chat_completions,
        list_models=system_endpoints_mod.list_models,
        health=system_endpoints_mod.health,
        live_key=system_endpoints_mod.live_key,
        router_status=system_endpoints_mod.router_status,
    )
