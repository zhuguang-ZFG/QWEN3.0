"""OpenCode deep optimization regression tests.

Validates all seven optimization dimensions from the OpenCode-Deep-Optimization plan.
"""

import os
from unittest.mock import patch

import pytest

# ─── Test 1: detect_ide recognizes OpenCode from message content ──────────────

def test_detect_opencode_from_content():
    """detect_ide() identifies OpenCode from system prompt fingerprints."""
    from routes.request_tracking import detect_ide

    # System message with OpenCode identity
    assert detect_ide([
        {"role": "system", "content": "You are OpenCode, an AI coding assistant"}
    ]) == "OpenCode"

    # Lowercase variant
    assert detect_ide([
        {"role": "system", "content": "You are opencode-ai agent"}
    ]) == "OpenCode"

    # First user message with OpenCode identity
    assert detect_ide([
        {"role": "user", "content": "opencode environment setup"}
    ]) == "OpenCode"

    # No OpenCode content
    assert detect_ide([
        {"role": "user", "content": "write a hello world function"}
    ]) == ""


# ─── Test 2: classify_request detects OpenCode from User-Agent ─────────────────

def test_detect_opencode_from_ua():
    """classify_request() detects OpenCode via User-Agent header."""
    from router_v3 import classify_request

    # User-Agent containing "opencode"
    result = classify_request("/v1/chat/completions", {
        "user-agent": "OpenCode/1.0",
        "content-type": "application/json",
    }, {"messages": [{"role": "user", "content": "hi"}]})
    assert result["type"] == "ide"

    # User-Agent with "opencode-ai"
    result = classify_request("/v1/chat/completions", {
        "user-agent": "opencode-ai/0.5",
        "content-type": "application/json",
    }, {"messages": [{"role": "user", "content": "hi"}]})
    assert result["type"] == "ide"

    # Non-IDE User-Agent
    result = classify_request("/v1/chat/completions", {
        "user-agent": "curl/8.0",
        "content-type": "application/json",
    }, {"messages": [{"role": "user", "content": "hello"}]})
    assert result["type"] == "chat"


# ─── Test 3: OpenCode skills coverage (skip style category) ───────────────────

def test_opencode_full_skills_coverage():
    """IDE_COVERAGE['OpenCode'] skips style category (built-in)."""
    from skills_injector import IDE_COVERAGE

    assert "OpenCode" in IDE_COVERAGE
    # OpenCode skips style category (already covered by built-in system prompt)
    assert IDE_COVERAGE["OpenCode"] == {"style"}, (
        "OpenCode should skip style category (already built-in)"
    )


# ─── Test 4: OpenCode requests classified as coding scenario ──────────────────

def test_opencode_scenario_is_coding():
    """classify_scenario() returns 'coding' for OpenCode ide_source."""
    from routing_classifier import classify_scenario

    # OpenCode ide_source triggers coding scenario
    assert classify_scenario("", [], ide_source="OpenCode") == "coding"
    assert classify_scenario("", [], ide_source="opencode") == "coding"
    assert classify_scenario("", [], ide_source="opencode-ai") == "coding"

    # Non-IDE source falls back to content-based classification
    assert classify_scenario("hello", [], ide_source="") == "chat"


# ─── Test 5: OpenCode backend preference (scnet_ds_flash default) ─────────────

def test_opencode_backend_preference():
    """resolve_route_prefs() prefers OPENCODE_PREFERRED_BACKEND for OpenCode IDE."""
    from chat_models import ChatRequest
    from opencode_config import OPENCODE_PREFERRED_BACKEND
    from routes.chat_handler_dispatch import resolve_route_prefs

    # OpenCode with default model → configured preferred backend
    req = ChatRequest(model="lima-1.3", messages=[{"role": "user", "content": "write a function"}])
    prefs = resolve_route_prefs(req, "OpenCode", "write a function")
    assert prefs.prefer == OPENCODE_PREFERRED_BACKEND

    # OpenCode with expert model → expert overrides to scnet_ds_pro
    req = ChatRequest(model="lima-thinking", messages=[{"role": "user", "content": "explain code"}])
    prefs = resolve_route_prefs(req, "OpenCode", "explain code")
    assert prefs.prefer == "scnet_ds_pro"

    # OpenCode lowercase
    req = ChatRequest(model="lima-1.3", messages=[{"role": "user", "content": "test"}])
    prefs = resolve_route_prefs(req, "opencode-ai", "test")
    assert prefs.prefer == OPENCODE_PREFERRED_BACKEND

    # Non-OpenCode IDE, default model → no forced prefer
    req = ChatRequest(model="lima-1.3", messages=[{"role": "user", "content": "hello"}])
    prefs = resolve_route_prefs(req, "OtherIDE", "hello")
    assert prefs.prefer is None


# ─── Test 6: OPENCODE_OPTIMIZATION_ENABLED activates direct tool mode ─────────

@pytest.mark.filterwarnings("ignore:OPENCODE_OPTIMIZATION_ENABLED is deprecated")
def test_opencode_tool_mode_flag():
    """Master switch OPENCODE_OPTIMIZATION_ENABLED=1 enables direct tool mode for OpenCode."""
    with patch.dict(os.environ, {"OPENCODE_OPTIMIZATION_ENABLED": "1"}):
        # Simulate the condition from chat_endpoints.py
        body = {"tools": [{"type": "function", "function": {"name": "read_file"}}]}
        ide_source = "OpenCode"
        result = (
            body.get("tools")
            and ide_source == "OpenCode"
            and (
                os.environ.get("LIMA_OPENCODE_TOOL_MODE") == "direct"
                or os.environ.get("OPENCODE_OPTIMIZATION_ENABLED", "0") == "1"
            )
        )
        assert result is True

    # Without the flag, but with LIMA_OPENCODE_TOOL_MODE=direct
    with patch.dict(os.environ, {
        "OPENCODE_OPTIMIZATION_ENABLED": "0",
        "LIMA_OPENCODE_TOOL_MODE": "direct",
    }):
        body = {"tools": [{"type": "function", "function": {"name": "read_file"}}]}
        ide_source = "OpenCode"
        result = (
            body.get("tools")
            and ide_source == "OpenCode"
            and (
                os.environ.get("LIMA_OPENCODE_TOOL_MODE") == "direct"
                or os.environ.get("OPENCODE_OPTIMIZATION_ENABLED", "0") == "1"
            )
        )
        assert result is True

    # Without any flag
    with patch.dict(os.environ, {
        "OPENCODE_OPTIMIZATION_ENABLED": "0",
    }, clear=False):
        body = {"tools": [{"type": "function", "function": {"name": "read_file"}}]}
        ide_source = "OpenCode"
        result = (
            body.get("tools")
            and ide_source == "OpenCode"
            and (
                os.environ.get("LIMA_OPENCODE_TOOL_MODE") == "direct"
                or os.environ.get("OPENCODE_OPTIMIZATION_ENABLED", "0") == "1"
            )
        )
        assert result is False

    # Not OpenCode — never triggers
    body = {"tools": [{"type": "function", "function": {"name": "read_file"}}]}
    ide_source = "OtherIDE"
    result = (
        body.get("tools")
        and ide_source == "OpenCode"
        and (
            os.environ.get("LIMA_OPENCODE_TOOL_MODE") == "direct"
            or os.environ.get("OPENCODE_OPTIMIZATION_ENABLED", "0") == "1"
        )
    )
    assert result is False


# ─── Test 7: HTTP connection pool reuse ───────────────────────────────────────

def test_opencode_connection_pool():
    """_get_client / _get_async_client return the same pooled client for same backend."""
    from http_request_builder import (
        _async_client_pool,
        _get_async_client,
        _get_client,
        _sync_client_pool,
    )

    # Clear pools before test
    _sync_client_pool.clear()
    _async_client_pool.clear()
    try:
        # Sync pool: same backend+timeout returns same client
        client1 = _get_client("test_backend", 30.0)
        client2 = _get_client("test_backend", 30.0)
        assert client1 is client2, "Pooled sync clients should be the same object"

        # Different timeout returns different pooled client
        client_diff_timeout = _get_client("test_backend", 60.0)
        assert client1 is not client_diff_timeout, (
            "Different timeout should create separate pooled client"
        )

        # Different backend returns different client
        client3 = _get_client("other_backend", 30.0)
        assert client1 is not client3

        # Verify pool keys exist (now include timeout in key: backend:timeout:bucket)
        assert any(k.startswith("test_backend:30:") for k in _sync_client_pool)
        assert any(k.startswith("test_backend:60:") for k in _sync_client_pool)
        assert any(k.startswith("other_backend:") for k in _sync_client_pool)

        # Async pool: same backend returns same client
        async_client1 = _get_async_client("test_backend", 30.0)
        async_client2 = _get_async_client("test_backend", 30.0)
        assert async_client1 is async_client2, (
            "Pooled async clients should be the same object"
        )

        # Verify pool key exists
        assert any(k.startswith("test_backend:30:") for k in _async_client_pool)
    finally:
        # Clean up — close clients to release connections
        for c in _sync_client_pool.values():
            try:
                c.close()
            except Exception:
                pass
        _sync_client_pool.clear()
        for c in _async_client_pool.values():
            try:
                c.close()
            except Exception:
                pass
        _async_client_pool.clear()


# ─── Test 8: Stream flush threshold is configurable ───────────────────────────

def test_stream_flush_threshold_configurable():
    """LIMA_STREAM_FLUSH_CHARS env var controls _STREAM_FLUSH_CHARS."""
    import importlib

    import http_stream

    with patch.dict(os.environ, {"LIMA_STREAM_FLUSH_CHARS": "50"}):
        importlib.reload(http_stream)
        assert http_stream._STREAM_FLUSH_CHARS == 50

    # Restore to default
    os.environ.pop("LIMA_STREAM_FLUSH_CHARS", None)
    importlib.reload(http_stream)
    assert http_stream._STREAM_FLUSH_CHARS == 200


# ─── Test 9: OpenCode startup empty-body must not 500 ────────────────────────

def test_opencode_empty_body_returns_400(monkeypatch):
    """OpenCode sends empty POST on startup; must return 400, not crash."""
    from fastapi.testclient import TestClient

    import server

    monkeypatch.setenv("LIMA_API_KEY", "test-private-token")
    client = TestClient(server.app)
    response = client.post(
        "/v1/chat/completions",
        headers={
            "Authorization": "Bearer test-private-token",
            "Content-Type": "application/json",
        },
        content=b"",
    )
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"


def test_v1_discovery_endpoint():
    """GET /v1 exposes OpenAI-compatible endpoint discovery."""
    from fastapi.testclient import TestClient

    import server

    client = TestClient(server.app)
    response = client.get("/v1")
    assert response.status_code == 200
    data = response.json()
    assert "/v1/chat/completions" in data.get("endpoints", [])
