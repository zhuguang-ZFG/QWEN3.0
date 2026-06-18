"""Guardrails for request pipeline module authority (REF-005)."""

from __future__ import annotations

import importlib
import inspect

import pytest


def test_routing_engine_exposes_route():
    routing_engine = importlib.import_module("routing_engine")
    assert hasattr(routing_engine, "route")
    assert callable(routing_engine.route)


def test_http_caller_is_transport_authority():
    http_caller = importlib.import_module("http_caller")
    assert hasattr(http_caller, "call_api")
    source = inspect.getsource(http_caller)
    assert "router_http" not in source


def test_backends_facade_removed_registry_is_authority():
    """backends.py facade retired; backends_registry is the authority."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backends")
    registry = importlib.import_module("backends_registry")
    assert hasattr(registry, "BACKENDS")


def test_lima_context_module_exports():
    """code_orchestrator retired; verify lima_context provides context building."""
    lima_ctx = importlib.import_module("lima_context")
    assert hasattr(lima_ctx, "build_context_digest")


def test_device_gateway_ws_split_preserves_exports():
    routes = importlib.import_module("routes.device_gateway")
    dispatch = importlib.import_module("routes.device_gateway_dispatch")
    ws = importlib.import_module("routes.device_gateway_ws")
    handlers = importlib.import_module("routes.device_gateway_ws_handlers")
    for name in ("_dispatch_task_to_session", "_drain_pending_tasks", "router"):
        assert hasattr(routes, name)
    assert hasattr(dispatch, "dispatch_task_to_session")
    assert hasattr(ws, "handle_device_ws")
    assert hasattr(handlers, "handle_transcript")


def test_streaming_bridge_split_preserves_exports():
    streaming = importlib.import_module("streaming")
    bridge = importlib.import_module("streaming_bridge")
    assert hasattr(streaming, "bridge_stream")
    assert hasattr(streaming, "speculative_stream")
    assert hasattr(bridge, "bridge_stream")
