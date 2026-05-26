"""Guardrails for request pipeline module authority (REF-005)."""

from __future__ import annotations

import importlib
import inspect


def test_routing_engine_exposes_route():
    routing_engine = importlib.import_module("routing_engine")
    assert hasattr(routing_engine, "route")
    assert callable(routing_engine.route)


def test_http_caller_is_transport_authority():
    http_caller = importlib.import_module("http_caller")
    assert hasattr(http_caller, "call_api")
    source = inspect.getsource(http_caller)
    assert "router_http" not in source


def test_backends_facade_reexports_registry():
    backends = importlib.import_module("backends")
    registry = importlib.import_module("backends_registry")
    assert backends.BACKENDS is registry.BACKENDS


def test_quality_gate_modules_are_distinct():
    root_qg = importlib.import_module("quality_gate")
    routes_pkg = importlib.import_module("routes.quality_gate")
    assert root_qg is not routes_pkg
    assert hasattr(root_qg, "check")
    assert hasattr(routes_pkg, "quality_check")


def test_code_orchestrator_context_split_preserves_exports():
    orchestrator = importlib.import_module("code_orchestrator")
    context = importlib.import_module("code_orchestrator_context")
    for name in ("POOLS", "classify_code_tier", "enhance_context", "handle"):
        assert hasattr(orchestrator, name)
        assert hasattr(context, name) or name == "handle"


def test_agent_task_evolution_routes_mounted():
    agent_tasks = importlib.import_module("routes.agent_tasks")
    evolution = importlib.import_module("routes.agent_task_evolution")
    paths = {getattr(r, "path", "") for r in agent_tasks.router.routes}
    assert any("/skills/candidates" in p for p in paths)
    assert hasattr(evolution, "list_skill_candidates")


def test_device_gateway_ws_split_preserves_exports():
    routes = importlib.import_module("routes.device_gateway")
    dispatch = importlib.import_module("routes.device_gateway_dispatch")
    ws = importlib.import_module("routes.device_gateway_ws")
    for name in ("_dispatch_task_to_session", "_drain_pending_tasks", "router"):
        assert hasattr(routes, name)
    assert hasattr(dispatch, "dispatch_task_to_session")
    assert hasattr(ws, "handle_device_ws")


def test_router_http_legacy_submodules():
    router_http = importlib.import_module("router_http")
    for submodule in ("router_http_body", "router_http_scnet", "router_http_vision"):
        importlib.import_module(submodule)
    assert hasattr(router_http, "call_api")
    assert hasattr(router_http, "_build_request_body")
