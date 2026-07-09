"""Tests for device app chat history and audio metadata routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_logic.audio_store import write_audio_file
from device_logic.db import _schema_ready_paths, connect
from device_logic.http import new_id, now


def _token(account_id: str) -> str:
    import time

    from device_logic.auth import jwt

    now_ts = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now_ts,
        "exp": now_ts + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id)}"}


def _seed() -> None:
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-owner', '13001', 'owner')")
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES ('a-guest', '13003', 'guest')")
        conn.execute(
            """
            INSERT INTO v2_device (id, device_sn, model, firmware_ver, hardware_ver)
            VALUES ('dev-1', 'SN-01', 'esp32s3_xyz', '1.0.0', 'rev-a')
            """
        )
        conn.execute(
            """
            INSERT INTO v2_device_binding (id, device_id, account_id, bind_mode, status)
            VALUES ('b-1', 'dev-1', 'a-owner', 'owner', 'active')
            """
        )
        session_id = new_id()
        conn.execute(
            """
            INSERT INTO v2_chat_session (id, device_id, account_id, title, created_at, status)
            VALUES (?, 'dev-1', 'a-owner', 'voice', ?, 'active')
            """,
            (session_id, now()),
        )
        conn.execute(
            """
            INSERT INTO v2_audio_record (id, device_id, session_id, audio_id, duration_ms, created_at)
            VALUES ('ar-1', 'dev-1', ?, 'audio-1', 1200, ?)
            """,
            (session_id, now()),
        )
        conn.execute(
            """
            INSERT INTO v2_chat_message (id, session_id, role, content, audio_id, created_at)
            VALUES ('msg-1', ?, 'user', 'hello voice', 'audio-1', ?)
            """,
            (session_id, now()),
        )
        conn.commit()


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "chat.db"))
    monkeypatch.setenv("LIMA_DATA_DIR", str(tmp_path / "lima-data"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    _schema_ready_paths.clear()
    from routes.device_app_chat import router as chat_router

    app = FastAPI()
    app.include_router(chat_router)
    return TestClient(app)


def _seed_with_audio_file(tmp_path) -> None:
    _seed()
    storage_path = write_audio_file("dev-1", "audio-1", b"fake-audio-bytes", ext="mp3")
    with connect() as conn:
        conn.execute(
            "UPDATE v2_audio_record SET storage_path=?, content_type=? WHERE audio_id='audio-1'",
            (storage_path, "audio/mpeg"),
        )
        conn.commit()


def test_chat_history_returns_audio_messages(client):
    _seed()
    response = client.get("/device/v1/app/devices/dev-1/chat-history", headers=_headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 1
    assert data["chatHistory"][0] == {"content": "hello voice", "audioId": "audio-1"}


def test_chat_history_denies_guest_without_share(client):
    _seed()
    response = client.get("/device/v1/app/devices/dev-1/chat-history", headers=_headers("a-guest"))
    assert response.status_code == 403


def test_audio_meta_requires_device_access(client, tmp_path):
    _seed_with_audio_file(tmp_path)
    response = client.get("/device/v1/app/audio/audio-1", headers=_headers("a-owner"))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["audioId"] == "audio-1"
    assert data["url"].endswith("/device/v1/app/audio/audio-1/content")

    denied = client.get("/device/v1/app/audio/audio-1", headers=_headers("a-guest"))
    assert denied.status_code == 403


def test_audio_content_streams_file(client, tmp_path):
    _seed_with_audio_file(tmp_path)
    response = client.get("/device/v1/app/audio/audio-1/content", headers=_headers("a-owner"))
    assert response.status_code == 200, response.text
    assert response.content == b"fake-audio-bytes"
    assert response.headers["content-type"].startswith("audio/mpeg")
