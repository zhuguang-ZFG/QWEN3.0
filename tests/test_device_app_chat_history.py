"""Tests for /device/v1/app chat history and transcript persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from device_app_helpers import client as make_client, headers, seed_account_and_device, seed_binding
from device_logic.chat_store import (
    create_session,
    insert_message,
    list_sessions,
)
from device_logic.db import connect


@pytest.fixture
def chat_client(tmp_path, monkeypatch):
    client, _store = make_client(tmp_path, monkeypatch)
    seed_account_and_device(device_id="d-chat", device_sn="SN-CHAT-01")
    seed_binding(device_id="d-chat", account_id="a-owner", binding_id="b-chat")
    return client


def _create_session(device_id: str = "d-chat", account_id: str = "a-owner", title: str = "") -> str:
    with connect() as conn:
        return create_session(conn, device_id, account_id, title)


def _insert_message(session_id: str, role: str, content: str, audio_id: str | None = None) -> str:
    with connect() as conn:
        return insert_message(conn, session_id, role, content, audio_id=audio_id)


def test_create_chat_session_requires_device_access(chat_client):
    response = chat_client.post("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-other"), json={})
    assert response.status_code == 403


def test_create_chat_session_without_title(chat_client):
    response = chat_client.post("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-owner"), json={})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deviceId"] == "d-chat"
    assert data["title"] == ""
    assert data["status"] == "active"


def test_create_chat_session_with_title(chat_client):
    response = chat_client.post(
        "/device/v1/app/devices/d-chat/chat-sessions",
        headers=headers("a-owner"),
        json={"title": "早安对话"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "早安对话"


def test_list_chat_sessions(chat_client):
    session_one = _create_session(title="session one")
    session_two = _create_session(title="session two")
    _insert_message(session_two, "user", "recent message")

    response = chat_client.get("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 2
    assert [s["title"] for s in data["sessions"]] == ["session two", "session one"]
    assert data["sessions"][0]["sessionId"] == session_two


def test_list_chat_sessions_requires_device_access(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-sessions", headers=headers("a-other"))
    assert response.status_code == 403


def test_get_chat_messages_paginated(chat_client):
    session_id = _create_session()
    _insert_message(session_id, "user", "hello")
    _insert_message(session_id, "assistant", "hi there")

    response = chat_client.get(
        f"/device/v1/app/devices/d-chat/chat-sessions/{session_id}/messages",
        headers=headers("a-owner"),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 2
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]


def test_get_chat_messages_pagination(chat_client):
    session_id = _create_session()
    for idx in range(3):
        _insert_message(session_id, "user", f"msg-{idx}")

    response = chat_client.get(
        f"/device/v1/app/devices/d-chat/chat-sessions/{session_id}/messages?limit=1&offset=1",
        headers=headers("a-owner"),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 1
    assert data["messages"][0]["content"] == "msg-1"


def test_get_chat_messages_wrong_session_returns_404(chat_client):
    response = chat_client.get(
        "/device/v1/app/devices/d-chat/chat-sessions/not-a-session/messages",
        headers=headers("a-owner"),
    )
    assert response.status_code == 404


def test_get_chat_messages_requires_device_access(chat_client):
    session_id = _create_session()
    response = chat_client.get(
        f"/device/v1/app/devices/d-chat/chat-sessions/{session_id}/messages",
        headers=headers("a-other"),
    )
    assert response.status_code == 403


def test_delete_chat_session(chat_client):
    session_id = _create_session()
    response = chat_client.delete(f"/device/v1/app/chat-sessions/{session_id}", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "deleted"

    with connect() as conn:
        rows = list_sessions(conn, "d-chat", "a-owner")
    assert len(rows) == 0


def test_delete_chat_session_wrong_owner(chat_client):
    session_id = _create_session()
    response = chat_client.delete(f"/device/v1/app/chat-sessions/{session_id}", headers=headers("a-other"))
    assert response.status_code == 404


def test_list_chat_history_returns_audio_messages(chat_client):
    session_id = _create_session()
    _insert_message(session_id, "user", "voice one", audio_id="audio-1.wav")
    _insert_message(session_id, "user", "voice two", audio_id="audio-2.wav")
    _insert_message(session_id, "assistant", "reply", audio_id="audio-3.wav")

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO v2_audio_record (id, device_id, session_id, audio_id, duration_ms, created_at)
            VALUES ('ar-1', 'd-chat', ?, 'audio-1.wav', 1234, datetime('now'))
            """,
            (session_id,),
        )
        conn.execute(
            """
            INSERT INTO v2_audio_record (id, device_id, session_id, audio_id, duration_ms, created_at)
            VALUES ('ar-2', 'd-chat', ?, 'audio-2.wav', 5678, datetime('now'))
            """,
            (session_id,),
        )
        conn.commit()

    response = chat_client.get("/device/v1/app/devices/d-chat/chat-history", headers=headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 2
    assert {m["audioId"] for m in data["chatHistory"]} == {"audio-1.wav", "audio-2.wav"}


def test_list_chat_history_requires_device_access(chat_client):
    response = chat_client.get("/device/v1/app/devices/d-chat/chat-history", headers=headers("a-other"))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_voice_transcript_persists_user_message(tmp_path, monkeypatch):
    from routes import ws_voice_transcript_helpers as vt

    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "transcript.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    from device_logic.db import _schema_ready_paths

    _schema_ready_paths.clear()

    seed_account_and_device(device_id="d-transcript", device_sn="SN-TRANSCRIPT-01")
    seed_binding(device_id="d-transcript", account_id="a-owner", binding_id="b-transcript")

    session = MagicMock()
    session.send_json = AsyncMock()
    session.websocket = MagicMock()
    session.websocket.send_bytes = AsyncMock()

    with (
        patch.object(vt, "_voice_enabled", return_value=True),
        patch(
            "device_voice.dialogue.process_text_utterance",
            return_value={"reply_text": "hi", "reply_audio": b""},
        ),
        patch.object(
            vt, "voice_status_frame", side_effect=lambda *a, **k: {"status": a[1] if len(a) > 1 else k.get("status")}
        ),
        patch.object(vt, "audio_reply_frame", return_value={"type": "audio"}),
    ):
        result = await vt.handle_voice_transcript(session, "d-transcript", "hello", "req-1")

    assert result is True

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT m.* FROM v2_chat_message m
            JOIN v2_chat_session s ON s.id = m.session_id
            WHERE s.device_id='d-transcript' AND m.role='user'
            """
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_voice_transcript_skips_persistence_without_binding(tmp_path, monkeypatch):
    from routes import ws_voice_transcript_helpers as vt

    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "transcript_empty.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    from device_logic.db import _schema_ready_paths

    _schema_ready_paths.clear()

    seed_account_and_device(device_id="d-orphan", device_sn="SN-ORPHAN-01")

    session = MagicMock()
    session.send_json = AsyncMock()
    session.websocket = MagicMock()
    session.websocket.send_bytes = AsyncMock()

    with (
        patch.object(vt, "_voice_enabled", return_value=True),
        patch(
            "device_voice.dialogue.process_text_utterance",
            return_value={"reply_text": "hi", "reply_audio": b""},
        ),
        patch.object(
            vt, "voice_status_frame", side_effect=lambda *a, **k: {"status": a[1] if len(a) > 1 else k.get("status")}
        ),
    ):
        result = await vt.handle_voice_transcript(session, "d-orphan", "hello", "req-1")

    assert result is True

    with connect() as conn:
        rows = conn.execute("SELECT * FROM v2_chat_session WHERE device_id='d-orphan'").fetchall()
    assert len(rows) == 0
