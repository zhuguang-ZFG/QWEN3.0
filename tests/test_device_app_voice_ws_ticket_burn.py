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


@pytest.mark.asyncio
async def test_consume_race_abandons_dashscope_session(monkeypatch):
    """Consume failure after ASR open must still close the DashScope session.

    Close code must remain 4401 after finalize (no blank second close).
    """
    from starlette.websockets import WebSocketState
    from device_voice.streaming_asr import DashScopeLiveStreamSession
    from routes.device_app_voice_ws import _run_voice_stream_ws

    closed = {"session": False, "ws_codes": []}
    session = object.__new__(DashScopeLiveStreamSession)

    async def _close():
        closed["session"] = True

    session.close = _close  # type: ignore[method-assign]

    async def _open():
        return session

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _open)
    monkeypatch.setattr("routes.device_app_voice_ws._consume_voice_ticket", lambda *_a, **_k: False)

    class _FakeWs:
        application_state = WebSocketState.CONNECTING
        query_params = {"ticket": "unused"}

        async def close(self, code: int = 1000, reason: str | None = None):
            closed["ws_codes"].append(code)
            # Leave CONNECTING: pre-accept close(4401) must not get a blank
            # finalize close() (default 1000) when state was not updated.

        async def accept(self, *a, **k):
            raise AssertionError("must not accept when consume fails")

        async def send_json(self, *a, **k):
            return None

    await _run_voice_stream_ws(_FakeWs(), {"id": "a-owner"})
    assert closed["session"] is True
    assert closed["ws_codes"] == [4401]


@pytest.mark.asyncio
async def test_dashscope_start_fail_keeps_close_1011(monkeypatch):
    """ASR start failure close(1011) must not be overwritten by finalize blank close."""
    from starlette.websockets import WebSocketState
    from device_voice.streaming_asr import DashScopeLiveStreamSession
    from routes.device_app_voice_ws import _run_voice_stream_ws

    closed = {"session": False, "ws_codes": []}
    session = object.__new__(DashScopeLiveStreamSession)

    async def _close():
        closed["session"] = True

    async def _start(_on_partial):
        raise RuntimeError("asr start boom")

    session.close = _close  # type: ignore[method-assign]
    session.start = _start  # type: ignore[method-assign]

    async def _open():
        return session

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _open)
    monkeypatch.setattr("routes.device_app_voice_ws._consume_voice_ticket", lambda *_a, **_k: True)

    class _FakeWs:
        application_state = WebSocketState.CONNECTING
        query_params = {"ticket": "unused"}

        async def close(self, code: int = 1000, reason: str | None = None):
            closed["ws_codes"].append(code)
            self.application_state = WebSocketState.DISCONNECTED

        async def accept(self):
            self.application_state = WebSocketState.CONNECTED

        async def send_json(self, *a, **k):
            return None

    await _run_voice_stream_ws(_FakeWs(), {"id": "a-owner"})
    assert closed["session"] is True
    assert closed["ws_codes"] == [1011]
