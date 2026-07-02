"""Tests for routes/device_gateway_ws_handlers.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from device_gateway.attestation import AttestationVerifier
from device_gateway.sessions import DeviceSession
from routes import device_gateway_ws_handlers as handlers
from routes import device_gateway_ws_motion as motion_handlers


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


# ── handle_hello ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_hello_success(websocket, monkeypatch):
    websocket.headers["authorization"] = "Bearer token-1"
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    message = {
        "type": "hello",
        "protocol": "lima-device-v1",
        "device_id": "dev-1",
        "fw_rev": "v1.3.0",
        "firmwareVersion": "v1.3.0",
        "firmwareHash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
        "capabilities": [],
    }
    with (
        patch.object(handlers, "drain_pending_tasks", new_callable=AsyncMock, return_value=True) as mock_drain,
        patch.object(handlers, "attestation_verifier", _isolated_verifier()),
    ):
        device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id == "dev-1"
    assert isinstance(session, DeviceSession)
    assert keep_open is True
    websocket.send_json.assert_awaited_once()
    mock_drain.assert_awaited_once_with(session)


def _isolated_verifier() -> AttestationVerifier:
    v = AttestationVerifier()
    v.register("v1.3.0", "sha256:" + "0" * 64)
    return v


@pytest.mark.asyncio
async def test_handle_hello_ticket_mismatch(websocket):
    websocket.scope["state"] = {"ticket_device_id": "dev-2"}
    message = {"type": "hello", "device_id": "dev-1"}
    device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id is None
    assert keep_open is False
    websocket.close.assert_awaited_once_with(code=1008)


@pytest.mark.asyncio
async def test_handle_hello_invalid_token(websocket, monkeypatch):
    websocket.headers["authorization"] = "Bearer bad-token"
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")
    message = {"type": "hello", "device_id": "dev-1"}
    device_id, session, keep_open = await handlers.handle_hello(websocket, message, request_id="r1")
    assert device_id is None
    assert keep_open is False
    websocket.close.assert_awaited_once_with(code=1008)


# ── handle_heartbeat ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_heartbeat(websocket):
    registry_session = MagicMock(spec=DeviceSession)
    registry_session.send_json = AsyncMock()
    handlers.registry.register(DeviceSession(device_id="dev-1", websocket=websocket))
    message = {"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 1000}
    await handlers.handle_heartbeat(websocket, "dev-1", message, request_id="r1")
    websocket.send_json.assert_awaited_once()
    payload = websocket.send_json.await_args.args[0]
    assert payload["type"] == "heartbeat_ack"
    assert payload["uptime_ms"] == 1000


# ── handle_transcript ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_transcript_with_text_chat_capability(websocket):
    session = DeviceSession(device_id="dev-1", websocket=websocket, capabilities=["text_chat"])
    handlers.registry.register(session)
    with patch.object(handlers, "handle_voice_transcript", new_callable=AsyncMock, return_value=True) as mock_voice:
        result = await handlers.handle_transcript(websocket, "dev-1", {"text": "hello"}, request_id="r1")
    assert result is True
    mock_voice.assert_awaited_once_with(session, "dev-1", "hello", "r1")


@pytest.mark.asyncio
async def test_handle_transcript_task_error(websocket):
    with patch.object(
        handlers,
        "create_task_from_transcript_async",
        new_callable=AsyncMock,
        return_value={"task_id": "t1", "error": "fail"},
    ):
        result = await handlers.handle_transcript(websocket, "dev-1", {"text": "hello"}, request_id="r1")
    assert result is True
    websocket.send_json.assert_awaited_once()
    assert websocket.send_json.await_args.args[0]["type"] == "motion_task_failed"


@pytest.mark.asyncio
async def test_handle_transcript_enqueues_when_no_session(websocket):
    task = {"task_id": "t1"}
    with (
        patch.object(
            handlers, "create_task_from_transcript_async", new_callable=AsyncMock, return_value=task
        ) as mock_create,
        patch.object(handlers, "enqueue_pending_task", return_value=1) as mock_enqueue,
    ):
        result = await handlers.handle_transcript(websocket, "dev-1", {"text": "hello"}, request_id="r1")
    assert result is False
    mock_enqueue.assert_called_once_with("dev-1", task)


# ── handle_motion_event ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_motion_event(websocket):
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    handlers.registry.register(session)
    message = {"type": "motion_event", "device_id": "dev-1", "task_id": "t1", "phase": "done"}
    with (
        patch.object(motion_handlers, "process_motion_event_core", return_value={"phase": "done"}),
        patch.object(motion_handlers, "execute_recovery", return_value=None),
        patch.object(motion_handlers, "record_outcome_ledger") as mock_ledger,
    ):
        await handlers.handle_motion_event("dev-1", message, request_id="r1")
    websocket.send_json.assert_awaited_once()
    assert websocket.send_json.await_args.args[0]["type"] == "motion_event_ack"
    mock_ledger.assert_called_once_with("dev-1", message, "done")


@pytest.mark.asyncio
async def test_handle_motion_event_recovery(websocket):
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    handlers.registry.register(session)
    message = {"type": "motion_event", "device_id": "dev-1", "task_id": "t1", "phase": "failed"}
    recovery = {"action": "retry", "attempt": 1}
    with (
        patch.object(motion_handlers, "process_motion_event_core", return_value={"phase": "failed"}),
        patch.object(motion_handlers, "execute_recovery", return_value=recovery),
        patch.object(motion_handlers, "send_recovery_ack", new_callable=AsyncMock) as mock_recovery_ack,
        patch.object(motion_handlers, "record_outcome_ledger") as mock_ledger,
    ):
        await handlers.handle_motion_event("dev-1", message, request_id="r1")
    mock_recovery_ack.assert_awaited_once()
    mock_ledger.assert_called_once_with("dev-1", message, "failed")


# ── handle_device_info ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_device_info(websocket):
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    handlers.registry.register(session)
    message = {"type": "device_info", "device_id": "dev-1", "model": "m5"}
    await handlers.handle_device_info("dev-1", message, request_id="r1")
    websocket.send_json.assert_awaited_once()
    assert websocket.send_json.await_args.args[0]["type"] == "device_info_ack"


# ── handle_self_check ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_self_check(websocket):
    session = DeviceSession(device_id="dev-1", websocket=websocket)
    handlers.registry.register(session)
    message = {"type": "self_check", "device_id": "dev-1", "status": "ok"}
    await handlers.handle_self_check("dev-1", message, request_id="r1")
    websocket.send_json.assert_awaited_once()
    payload = websocket.send_json.await_args.args[0]
    assert payload["type"] == "self_check_ack"
    assert payload["status"] == "ok"


# ── module exports ───────────────────────────────────────────────────────


def test_module_exports():
    assert "handle_hello" in handlers.__all__
    assert "handle_heartbeat" in handlers.__all__
    assert "handle_transcript" in handlers.__all__
