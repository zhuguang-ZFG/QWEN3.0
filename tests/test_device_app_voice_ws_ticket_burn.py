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


def _pass_voice_validate(monkeypatch) -> None:
    monkeypatch.setattr("routes.device_app_voice_ws.validate_voice_stream_available", lambda: None)


def test_voice_ws_slot_full_does_not_burn_ticket(tmp_path, monkeypatch):
    """Slot-full (4429) must leave ticket reusable for a later successful connect."""
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    _pass_voice_validate(monkeypatch)
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

    def _asr_unavailable():
        raise AsrNotConfiguredError("ASR disabled for test")

    monkeypatch.setattr("routes.device_app_voice_ws.validate_voice_stream_available", _asr_unavailable)
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
    _pass_voice_validate(monkeypatch)
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
async def test_consume_fail_after_start_closes_4401(monkeypatch):
    """Consume failure after ASR start must close 4401 and teardown session."""
    from starlette.websockets import WebSocketState
    from device_voice.streaming_asr import DashScopeLiveStreamSession
    from routes.device_app_voice_ws import _run_voice_stream_ws

    closed = {"session": False, "ws_codes": [], "opened": False}
    session = object.__new__(DashScopeLiveStreamSession)

    async def _close():
        closed["session"] = True

    async def _start(_on_partial):
        return None

    session.close = _close  # type: ignore[method-assign]
    session.start = _start  # type: ignore[method-assign]

    async def _open():
        closed["opened"] = True
        return session

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _open)
    monkeypatch.setattr("routes.device_app_voice_ws._consume_voice_ticket", lambda *_a, **_k: False)
    _pass_voice_validate(monkeypatch)

    class _FakeWs:
        application_state = WebSocketState.CONNECTING
        query_params = {"ticket": "unused"}

        async def close(self, code: int = 1000, reason: str | None = None):
            closed["ws_codes"].append(code)
            self.application_state = WebSocketState.DISCONNECTED

        async def accept(self, *a, **k):
            self.application_state = WebSocketState.CONNECTED

        async def send_json(self, *a, **k):
            return None

    await _run_voice_stream_ws(_FakeWs(), {"id": "a-owner"})
    assert closed["opened"] is True
    assert closed["session"] is True
    assert closed["ws_codes"] == [4401]


@pytest.mark.asyncio
async def test_dashscope_start_fail_keeps_close_1011(monkeypatch):
    """ASR start failure close(1011) must not be overwritten by finalize blank close."""
    from starlette.websockets import WebSocketState
    from device_voice.streaming_asr import DashScopeLiveStreamSession
    from routes.device_app_voice_ws import _run_voice_stream_ws

    closed = {"session": False, "ws_codes": [], "consumed": False}
    session = object.__new__(DashScopeLiveStreamSession)

    async def _close():
        closed["session"] = True

    async def _start(_on_partial):
        raise RuntimeError("asr start boom")

    session.close = _close  # type: ignore[method-assign]
    session.start = _start  # type: ignore[method-assign]

    async def _open():
        return session

    def _consume(*_a, **_k):
        closed["consumed"] = True
        return True

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _open)
    monkeypatch.setattr("routes.device_app_voice_ws._consume_voice_ticket", _consume)
    _pass_voice_validate(monkeypatch)

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
    assert closed["consumed"] is False
    assert closed["ws_codes"] == [1011]


def test_voice_ws_asr_start_fail_does_not_burn_ticket(tmp_path, monkeypatch):
    """DashScope session.start failure must leave ticket reusable."""
    from device_voice.streaming_asr import DashScopeLiveStreamSession

    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    _pass_voice_validate(monkeypatch)

    session = object.__new__(DashScopeLiveStreamSession)

    async def _start(_on_partial):
        raise RuntimeError("asr start boom")

    async def _close():
        return None

    session.start = _start  # type: ignore[method-assign]
    session.close = _close  # type: ignore[method-assign]

    async def _open():
        return session

    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _open)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    # Accept happens before start; start fail closes 1011 without burning ticket.
    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}"):
        pass
    assert voice_app_ws_ticket.peek(ticket) == "a-owner"
