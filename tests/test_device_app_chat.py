"""Tests for /device/v1/app chat history and audio routes."""

from __future__ import annotations

import pytest

from device_app_helpers import client as make_client, headers, seed_account_and_device, seed_binding


@pytest.fixture
def chat_client(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device(device_id="d-chat", device_sn="SN-CHAT-01")
    seed_binding(device_id="d-chat", account_id="a-owner", binding_id="b-chat")
    return client


def test_list_chat_sessions_requires_device_access(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-other"))
    assert response.status_code == 403


def test_list_chat_sessions_returns_empty(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-owner"))
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == []
    assert data["count"] == 0


def test_get_chat_messages_returns_empty(chat_client):
    response = chat_client.get(
        "/device/v1/app/devices/d-chat/chat-sessions/s-1/messages",
        headers=headers("a-owner"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["sessionId"] == "s-1"


def test_get_audio_info_requires_auth(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/audio/abc.wav")
    assert response.status_code == 401


def test_get_audio_info_requires_device_access(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/audio/abc.wav", headers=headers("a-other"))
    assert response.status_code == 403


def test_get_audio_info_returns_url_when_upload_exists(chat_client, tmp_path, monkeypatch):
    import uuid

    from routes import upload as upload_mod

    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setattr(upload_mod, "_UPLOAD_DIR", tmp_path / "uploads")
    upload_mod._UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    audio_id = f"{uuid.uuid4().hex}.wav"
    (upload_mod._UPLOAD_DIR / audio_id).write_bytes(b"fake-wav")

    response = chat_client.get(f"/device/v1/app/devices/d-chat/audio/{audio_id}", headers=headers("a-owner"))
    assert response.status_code == 200
    data = response.json()
    assert data["audioId"] == audio_id
    assert f"/uploads/{audio_id}?token=" in data["url"]


def test_list_chat_history_returns_empty(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-history", headers=headers("a-owner"))
    assert response.status_code == 200
    data = response.json()
    assert data["chatHistory"] == []
    assert data["count"] == 0


def test_list_chat_history_requires_device_access(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-history", headers=headers("a-other"))
    assert response.status_code == 403
