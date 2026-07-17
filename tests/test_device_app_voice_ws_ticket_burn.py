"""Voice WS ticket burn semantics: fail paths must not consume; success must."""

from __future__ import annotations

from dataclasses import replace

import pytest
import voice_app_ws_ticket
import voice_ws_connections
from config.voice_settings import VOICE
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device


class _FakeBufferedSession:
    async def feed(self, chunk: bytes) -> None:
        return None

    async def finish(self) -> str:
        return "你好世界"


async def _fake_open_session():
    return _FakeBufferedSession()


def test_voice_ws_slot_full_does_not_burn_ticket(tmp_path, monkeypatch):
    """Slot-full (4429) must leave ticket reusable for a later successful connect."""
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    monkeypatch.setattr("routes.device_app_voice_ws.VOICE", replace(VOICE, ws_max_concurrent=1))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket_one = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]
    ticket_two = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket_one}") as first:
        with pytest.raises(Exception):
            with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket_two}"):
                pass
        assert voice_app_ws_ticket.peek(ticket_two) == "a-owner"
        first.send_text("stop")
        first.receive_json()

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket_two}") as websocket:
        websocket.send_text("stop")
        assert websocket.receive_json()["type"] == "transcript"
    assert voice_app_ws_ticket.peek(ticket_two) is None


def test_voice_ws_asr_unavailable_does_not_burn_ticket(tmp_path, monkeypatch):
    from device_voice.asr import AsrNotConfiguredError

    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()

    async def _asr_unavailable():
        raise AsrNotConfiguredError("ASR disabled for test")

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _asr_unavailable)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with pytest.raises(Exception):
        with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}"):
            pass
    assert voice_app_ws_ticket.peek(ticket) == "a-owner"
    assert voice_ws_connections.count("a-owner") == 0


def test_voice_ws_success_consumes_ticket(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        websocket.send_text("stop")
        assert websocket.receive_json()["type"] == "transcript"

    assert voice_app_ws_ticket.peek(ticket) is None
    with pytest.raises(Exception):
        with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}"):
            pass
