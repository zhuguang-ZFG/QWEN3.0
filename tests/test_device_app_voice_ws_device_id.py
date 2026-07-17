"""Voice WS optional device_id / community device-id aliases."""

from __future__ import annotations

import pytest
import voice_app_ws_ticket
from device_app_helpers import client as make_client
from device_app_helpers import headers, seed_account_and_device, seed_binding


class _FakeBufferedSession:
    async def feed(self, chunk: bytes) -> None:
        return None

    async def finish(self) -> str:
        return "你好世界"


async def _fake_open_session():
    return _FakeBufferedSession()


@pytest.fixture(autouse=True)
def _voice_stream_available(monkeypatch):
    import routes.device_app_voice_ws as voice_ws

    monkeypatch.setattr(voice_ws, "validate_voice_stream_available", lambda: None)


def test_voice_ws_rejects_unbound_device_id(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with pytest.raises(Exception):
        with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}&device_id=dev-1"):
            pass
    assert voice_app_ws_ticket.peek(ticket) == "a-owner"


def test_voice_ws_accepts_bound_device_id(tmp_path, monkeypatch):
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}&device_id=dev-1") as websocket:
        websocket.send_text("stop")
        message = websocket.receive_json()
        assert message["type"] == "transcript"


def test_voice_ws_accepts_community_device_id_aliases(tmp_path, monkeypatch):
    """Query device-id / header device-id (xiaozhi-esp32-server community style)."""
    voice_app_ws_ticket.reset()
    monkeypatch.setattr("routes.device_app_voice_ws.open_voice_stream_session", _fake_open_session)
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device()
    seed_binding()
    ticket = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]

    with client.websocket_connect(f"/device/v1/app/voice/ws?ticket={ticket}&device-id=dev-1") as websocket:
        websocket.send_text("stop")
        assert websocket.receive_json()["type"] == "transcript"

    ticket2 = client.post("/device/v1/app/voice/ticket", headers=headers("a-owner")).json()["ticket"]
    with client.websocket_connect(
        f"/device/v1/app/voice/ws?ticket={ticket2}",
        headers={"device-id": "dev-1"},
    ) as websocket:
        websocket.send_text("stop")
        assert websocket.receive_json()["type"] == "transcript"
