"""Tests for routes/route_registry.py (CQ-014 slice 3)."""

from fastapi.routing import APIRoute

import routes.route_registry as route_registry
import server


def _api_paths() -> set[str]:
    return {
        route.path
        for route in server.app.routes
        if isinstance(route, APIRoute)
    }


def test_server_registers_core_routes_via_registry():
    paths = _api_paths()
    expected = {
        "/v1/chat/completions",
        "/v1/messages",
        "/v1/models",
        "/v1/embeddings",
        "/health",
        "/admin",
        "/v1/images/generations",
    }
    assert expected.issubset(paths)


def test_registry_exports_handler_aliases():
    import routes.chat_endpoints as chat_endpoints
    import routes.system_endpoints as system_endpoints

    assert server.chat_completions is chat_endpoints.chat_completions
    assert server.anthropic_messages is chat_endpoints.anthropic_messages
    assert server.health is system_endpoints.health
    assert server.list_models is system_endpoints.list_models


def test_registry_marks_device_gateway_loaded():
    assert server._loaded_modules.get("device_gateway") is True


def test_server_registers_xiaozhi_v1_compat_routes():
    paths = _api_paths()

    assert "/api/v1/login" in paths
    assert server._loaded_modules.get("xiaozhi_v1_compat") is True


def test_register_all_routes_is_idempotent_on_fresh_app():
    from fastapi import FastAPI
    import routes.chat_endpoints as chat_endpoints_mod
    import routes.system_endpoints as system_endpoints_mod

    saved_deps = dict(chat_endpoints_mod._deps)
    saved_modules = system_endpoints_mod._loaded_modules
    saved_model_id = system_endpoints_mod._model_id
    saved_model_created = system_endpoints_mod._model_created
    try:
        app = FastAPI()
        deps = route_registry.RouteRegistryDeps(
            model_id="test",
            model_created=0,
            stats={},
            stats_lock=server._stats_lock,
            backend_enabled={},
            loaded_modules={},
            client_ip=lambda request: "127.0.0.1",
            detect_ide=lambda messages: "test",
            elapsed_ms=lambda started_at: 0,
            vision_route=lambda *args, **kwargs: None,
            stream_vision_response=lambda *args, **kwargs: iter([]),
            record_request=lambda *args, **kwargs: None,
            anthropic_native_stream=lambda body: iter([]),
            anthropic_native_forward=lambda body: {},
            anthropic_stream=lambda *args, **kwargs: iter([]),
            anthropic_stream_passthrough=lambda body, model: iter([]),
            handle_chat=lambda *args, **kwargs: {},
        )
        registered = route_registry.register_all_routes(app, deps)
        paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
        assert "/v1/chat/completions" in paths
        assert "/api/v1/login" in paths
        assert deps.loaded_modules.get("xiaozhi_v1_compat") is True
        assert registered.health is not None
    finally:
        chat_endpoints_mod._deps.clear()
        chat_endpoints_mod._deps.update(saved_deps)
        system_endpoints_mod._loaded_modules = saved_modules
        system_endpoints_mod._model_id = saved_model_id
        system_endpoints_mod._model_created = saved_model_created
