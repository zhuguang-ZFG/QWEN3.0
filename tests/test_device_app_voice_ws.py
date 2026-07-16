"""Tests for device app voice streaming WebSocket."""

from __future__ import annotations

from dataclasses import replace

import pytest
import voice_app_ws_ticket
import voice_ws_connections
from config.voice_settings import VOICE
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device
from device_logic.db import connect


class _FakeBufferedSession:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    async def feed(self, chunk: bytes) -> None:
        if chunk:
            self.chunks.append(chunk)

    async def finish(self) -> str:
        return "你好世界"


class _FakeRuntimeErrorSession:
    async def feed(self, chunk: bytes) -> None:
        return None

    async def finish(self) -> str:
        raise RuntimeError("ASR returned empty transcript")


async def _fake_open_session():
    return _FakeBufferedSession()


async def _fake_open_runtime_error_session():
    return _FakeRuntimeErrorSession()


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


def test_voice_ws_ping_pong(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        websocket.send_text("ping")
        message = websocket.receive_json()
        assert message == {"type": "pong"}
        websocket.send_text("stop")
        transcript = websocket.receive_json()
        assert transcript["type"] == "transcript"


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


def test_voice_ws_invalid_account_preserves_ticket(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = voice_app_ws_ticket.issue("a-owner")
    with connect() as conn:
        conn.execute("UPDATE v2_account SET status='disabled' WHERE id='a-owner'")
        conn.commit()

    with pytest.raises(Exception):
        with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}"):
            pass

    assert voice_app_ws_ticket.peek(ticket) == "a-owner"


def test_voice_ws_rejects_when_connect_rate_limited(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    monkeypatch.setattr("routes.device_app_voice_ws._allow_voice_ws_connect", lambda _account_id: False)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with pytest.raises(Exception):
        with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}"):
            pass


def test_voice_ws_rejects_when_concurrent_limit_reached(tmp_path, monkeypatch):
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
        first.send_text("stop")
        first.receive_json()


def test_voice_ws_stop_runtime_error_returns_message(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_runtime_error_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        websocket.send_text("stop")
        message = websocket.receive_json()
        assert message == {"type": "error", "message": "ASR returned empty transcript"}


def test_voice_ws_rejects_oversized_frame(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    monkeypatch.setattr("routes.device_app_voice_ws.VOICE", replace(VOICE, max_audio_bytes=16))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        websocket.send_bytes(b"\x00\x01" * 20)
        message = websocket.receive_json()
        assert message["type"] == "error"
        assert "max size" in message["message"]


def test_voice_ws_session_data_limit_exceeded(tmp_path, monkeypatch):
    """Sending cumulative bytes exceeding VOICE.max_audio_bytes * 10 closes with 1009."""
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    monkeypatch.setattr("routes.device_app_voice_ws.VOICE", replace(VOICE, max_audio_bytes=100))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        # 11 frames x 100 bytes = 1100 > 1000 session limit
        for _ in range(11):
            websocket.send_bytes(b"x" * 100)
        message = websocket.receive_json()
        assert message["type"] == "error"
        assert "session audio data limit exceeded" in message["message"]


def test_voice_ws_session_data_under_limit_ok(tmp_path, monkeypatch):
    """Cumulative bytes within VOICE.max_audio_bytes * 10 works normally."""
    voice_app_ws_ticket.reset()
    voice_ws_connections.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    monkeypatch.setattr("routes.device_app_voice_ws.VOICE", replace(VOICE, max_audio_bytes=100))
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}") as websocket:
        # 9 frames x 100 bytes = 900, under the 1000 session limit
        for _ in range(9):
            websocket.send_bytes(b"x" * 100)
        websocket.send_text("stop")
        transcript = websocket.receive_json()
        assert transcript["type"] == "transcript"


async def test_finalize_dashscope_close_error_does_not_propagate():
    """#3 回归：DashScope close() 超时/抛异常时不得穿透 _finalize_voice_session，
    且必须仍调用 websocket.close()（否则连接槽泄漏）。"""
    from starlette.websockets import WebSocketState
    from device_voice.streaming_asr import DashScopeLiveStreamSession
    from routes.device_app_voice_ws import _finalize_voice_session

    # 造壳绕过 __init__，仅让 isinstance 命中 DashScope 分支。
    session = object.__new__(DashScopeLiveStreamSession)

    async def _boom():
        raise RuntimeError("dashscope stop hung")

    session.close = _boom  # type: ignore[method-assign]

    closed = {"called": False}

    class _FakeWs:
        application_state = WebSocketState.CONNECTED
        client_state = WebSocketState.CONNECTED

        async def close(self, *a, **k):
            closed["called"] = True

        async def send_json(self, *a, **k):
            return None

    # 不得抛异常；异常被吞后仍须关闭 websocket。
    await _finalize_voice_session(_FakeWs(), session)
    assert closed["called"] is True
