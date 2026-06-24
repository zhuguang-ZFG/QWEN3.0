"""Tests for protocol version negotiation and firmware capability matrix (F2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from device_gateway.firmware_matrix import (
    COMPATIBILITY_MATRIX,
    get_supported_capabilities,
    is_capability_available,
)
from device_gateway.protocol_negotiator import (
    SUPPORTED_PROTOCOLS,
    ProtocolNegotiator,
)
from device_gateway.sessions import DeviceSession
from routes import device_gateway_ws_handlers as handlers


class TestProtocolNegotiator:
    def test_supported_protocols_constant(self) -> None:
        assert SUPPORTED_PROTOCOLS == ["lima-device-v1", "lima-device-v2-draft"]

    def test_negotiate_selects_v2_when_device_advertises_v2(self) -> None:
        negotiator = ProtocolNegotiator()
        assert negotiator.negotiate("lima-device-v2-draft", "v1.3.0") == "lima-device-v2-draft"

    def test_negotiate_selects_v1_when_device_advertises_v1(self) -> None:
        negotiator = ProtocolNegotiator()
        assert negotiator.negotiate("lima-device-v1", "v1.0.0") == "lima-device-v1"

    def test_negotiate_fallback_for_unknown_protocol(self) -> None:
        negotiator = ProtocolNegotiator()
        assert negotiator.negotiate("lima-device-v3", "v1.3.0") == "lima-device-v1"
        assert negotiator.negotiate("", "v1.3.0") == "lima-device-v1"

    def test_capabilities_for_v1(self) -> None:
        negotiator = ProtocolNegotiator()
        caps = negotiator.capabilities_for_version("lima-device-v1")
        assert "run_path" in caps
        assert "voice_command" not in caps
        assert "multi_pass" not in caps

    def test_capabilities_for_v2(self) -> None:
        negotiator = ProtocolNegotiator()
        caps = negotiator.capabilities_for_version("lima-device-v2-draft")
        expected = {
            "run_path", "write_text", "draw_generated", "draw_asset",
            "home", "pause", "resume", "stop", "get_device_info",
            "self_check", "estop", "voice_command",
            "multi_pass", "variable_speed",
        }
        assert caps == expected

    def test_capabilities_for_unknown_version_defaults_to_v1(self) -> None:
        negotiator = ProtocolNegotiator()
        assert negotiator.capabilities_for_version("lima-device-v99") == negotiator.capabilities_for_version("lima-device-v1")


class TestFirmwareMatrix:
    def test_matrix_contains_expected_versions(self) -> None:
        assert set(COMPATIBILITY_MATRIX.keys()) >= {"v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0"}

    def test_get_supported_capabilities_known_versions(self) -> None:
        assert "run_path" in get_supported_capabilities("v1.0.0")
        assert "draw_generated" in get_supported_capabilities("v1.1.0")
        assert "draw_asset" in get_supported_capabilities("v1.2.0")
        assert "estop" in get_supported_capabilities("v1.3.0")

    def test_get_supported_capabilities_unknown_version_returns_empty(self) -> None:
        assert get_supported_capabilities("v9.9.9") == frozenset()

    def test_is_capability_available(self) -> None:
        assert is_capability_available("estop", "v1.3.0") is True
        assert is_capability_available("estop", "v1.2.0") is False
        assert is_capability_available("run_path", "v1.0.0") is True
        assert is_capability_available("multi_pass", "v1.3.0") is False


@pytest.fixture
def websocket():
    ws = MagicMock(spec=WebSocket)
    ws.scope = {}
    ws.query_params = MagicMock()
    ws.query_params.get.return_value = ""
    ws.headers = {}
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture(autouse=True)
def _reset_registry():
    handlers.registry.clear()
    handlers.shadow_store.reset()
    yield
    handlers.registry.clear()
    handlers.shadow_store.reset()


@pytest.mark.asyncio
async def test_handle_hello_returns_negotiated_protocol_and_capabilities(websocket, monkeypatch):
    websocket.headers["authorization"] = "Bearer token-1"
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    message = {
        "type": "hello",
        "protocol": "lima-device-v2-draft",
        "device_id": "dev-1",
        "fw_rev": "v1.3.0",
        "capabilities": [],
    }
    with patch.object(handlers, "drain_pending_tasks", new_callable=AsyncMock, return_value=True):
        device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")

    assert device_id == "dev-1"
    assert keep_open is True
    assert isinstance(session, DeviceSession)
    assert session.protocol_version == "lima-device-v2-draft"
    assert "voice_command" in session.negotiated_capabilities

    websocket.send_json.assert_awaited_once()
    payload = websocket.send_json.await_args.args[0]
    assert payload["type"] == "hello_ack"
    assert payload["protocol"] == "lima-device-v2-draft"
    assert "capabilities" in payload
    assert "voice_command" in payload["capabilities"]


@pytest.mark.asyncio
async def test_handle_hello_unknown_protocol_falls_back_to_v1(websocket, monkeypatch):
    websocket.headers["authorization"] = "Bearer token-1"
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    message = {
        "type": "hello",
        "protocol": "lima-device-v99",
        "device_id": "dev-1",
        "fw_rev": "v1.0.0",
        "capabilities": [],
    }
    with patch.object(handlers, "drain_pending_tasks", new_callable=AsyncMock, return_value=True):
        _, session, _ = await handlers.handle_hello(websocket, message, request_id="r1")

    assert session.protocol_version == "lima-device-v1"
    assert "voice_command" not in session.negotiated_capabilities
