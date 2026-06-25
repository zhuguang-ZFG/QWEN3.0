"""Tests for routes/device_gateway_ws.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from device_gateway.protocol import ProtocolError
from routes import device_gateway_ws as dgws


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_DEVICE_TOKENS", "dev-1=token-1")

    router = APIRouter(prefix="/device/v1")
    router.websocket("/ws")(dgws.handle_device_ws)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_websocket_route_accepts_and_receives(client):
    with (
        patch.object(
            dgws, "handle_hello", new_callable=AsyncMock, return_value=("dev-1", MagicMock(), True)
        ) as mock_hello,
        patch.object(dgws, "handle_heartbeat", new_callable=AsyncMock) as mock_heartbeat,
        patch.object(dgws, "requeue_session_outstanding") as mock_requeue,
        patch.object(dgws, "_cleanup_audio_registry") as mock_cleanup,
    ):
        with client.websocket_connect("/device/v1/ws") as ws:
            ws.send_json({"type": "hello", "protocol": "lima-device-v1", "device_id": "dev-1"})
            ws.send_json({"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 1000})
    mock_hello.assert_awaited_once()
    mock_heartbeat.assert_awaited_once()
    mock_requeue.assert_called_once()
    mock_cleanup.assert_called_once_with("dev-1")


def test_websocket_route_invalid_json(client):
    with (
        patch.object(dgws, "send_ws_error", new_callable=AsyncMock) as mock_send_error,
        patch.object(dgws, "requeue_session_outstanding"),
    ):
        with client.websocket_connect("/device/v1/ws") as ws:
            ws.send_text("not-json")
    mock_send_error.assert_awaited_once()
    payload = mock_send_error.await_args.args[1]
    assert isinstance(payload, ProtocolError)
    assert payload.code == "E_INVALID_JSON"


@pytest.mark.asyncio
async def test_handle_device_ws_hello_then_disconnect():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.receive = AsyncMock(
        side_effect=[
            {"type": "websocket.receive", "text": '{"type":"hello","protocol":"lima-device-v1","device_id":"dev-1"}'},
            {"type": "websocket.disconnect"},
        ]
    )
    websocket.send_json = AsyncMock()
    websocket.close = AsyncMock()

    with (
        patch.object(
            dgws, "handle_hello", new_callable=AsyncMock, return_value=("dev-1", MagicMock(), True)
        ) as mock_hello,
        patch.object(dgws, "requeue_session_outstanding") as mock_requeue,
        patch.object(dgws, "_cleanup_audio_registry") as mock_cleanup,
        patch.object(dgws.registry, "unregister") as mock_unregister,
    ):
        await dgws.handle_device_ws(websocket)

    websocket.accept.assert_awaited_once()
    mock_hello.assert_awaited_once()
    mock_requeue.assert_called_once()
    mock_cleanup.assert_called_once_with("dev-1")
    mock_unregister.assert_called_once_with("dev-1", websocket)


@pytest.mark.asyncio
async def test_handle_device_ws_binary_audio():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.receive = AsyncMock(
        side_effect=[
            {"type": "websocket.receive", "text": '{"type":"hello","protocol":"lima-device-v1","device_id":"dev-1"}'},
            {"type": "websocket.receive", "bytes": b"audio-data"},
            {"type": "websocket.disconnect"},
        ]
    )
    websocket.send_json = AsyncMock()
    websocket.close = AsyncMock()

    with (
        patch.object(dgws, "handle_hello", new_callable=AsyncMock, return_value=("dev-1", MagicMock(), True)),
        patch.object(dgws, "_feed_audio_to_pipeline", new_callable=AsyncMock) as mock_feed,
        patch.object(dgws, "requeue_session_outstanding") as mock_requeue,
        patch.object(dgws, "_cleanup_audio_registry") as mock_cleanup,
    ):
        await dgws.handle_device_ws(websocket)

    mock_feed.assert_awaited_once_with(websocket, "dev-1", b"audio-data")


@pytest.mark.asyncio
async def test_handle_text_frame_hello_required():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    raw = {"type": "heartbeat", "device_id": "dev-1", "uptime_ms": 1000}
    with patch.object(dgws, "send_ws_error", new_callable=AsyncMock) as mock_send_error:
        device_id, session, authenticated, keep_open = await dgws._handle_text_frame(websocket, raw, None, None, False)
    assert device_id is None
    assert authenticated is False
    assert keep_open is True
    mock_send_error.assert_awaited_once()
    assert mock_send_error.await_args.args[1].code == "E_HELLO_REQUIRED"


@pytest.mark.asyncio
async def test_handle_text_frame_device_mismatch():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    raw = {"type": "heartbeat", "device_id": "dev-2", "uptime_ms": 1000}
    with patch.object(dgws, "send_ws_error", new_callable=AsyncMock) as mock_send_error:
        device_id, session, authenticated, keep_open = await dgws._handle_text_frame(
            websocket, raw, "dev-1", MagicMock(), True
        )
    assert device_id == "dev-1"
    assert authenticated is True
    assert keep_open is True
    mock_send_error.assert_awaited_once()
    assert mock_send_error.await_args.args[1].code == "E_DEVICE_MISMATCH"


@pytest.mark.asyncio
async def test_handle_text_frame_protocol_error():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    raw = {"type": "bad"}
    with (
        patch.object(dgws, "validate_uplink", side_effect=ProtocolError("E_UNSUPPORTED_TYPE", "bad")) as mock_validate,
        patch.object(dgws, "send_ws_error", new_callable=AsyncMock) as mock_send_error,
    ):
        await dgws._handle_text_frame(websocket, raw, None, None, False)
    mock_validate.assert_called_once_with(raw)
    mock_send_error.assert_awaited_once()
