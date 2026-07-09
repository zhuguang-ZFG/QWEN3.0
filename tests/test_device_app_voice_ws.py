"""Tests for device app voice streaming WebSocket."""

from __future__ import annotations

import pytest
import voice_app_ws_ticket
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device


class _FakeBufferedSession:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    async def feed(self, chunk: bytes) -> None:
        if chunk:
            self.chunks.append(chunk)

    async def finish(self) -> str:
        return "你好世界"


async def _fake_open_session():
    return _FakeBufferedSession()


def test_voice_ws_rejects_missing_ticket(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    with pytest.raises(Exception):
        with client.websocket_connect("/device/v1/app/voice/ws"):
            pass


def test_voice_ws_streams_transcript(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket_resp = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner"))
    ticket = ticket_resp.json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        websocket.send_bytes(b"\x00\x00" * 16)
        websocket.send_text("stop")
        message = websocket.receive_json()
        assert message["type"] == "transcript"
        assert message["text"] == "你好世界"
        assert message["is_final"] is True


def test_legacy_v1_voice_alias(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/v1/voice?ticket={ticket}") as websocket:
        websocket.send_bytes(b"\x00\x00" * 16)
        websocket.send_text("stop")
        message = websocket.receive_json()
        assert message["type"] == "transcript"
        assert message["text"] == "你好世界"


def test_authenticate_websocket_returns_voice_account_id():
    from access_guard import authenticate_websocket

    voice_app_ws_ticket.reset()
    ticket = voice_app_ws_ticket.issue("a-owner")

    class FakeWebSocket:
        headers = {}
        query_params = {"ticket": ticket}

    ok, method, account_id = authenticate_websocket(FakeWebSocket())
    assert ok is True
    assert method == "ticket"
    assert account_id == "a-owner"
