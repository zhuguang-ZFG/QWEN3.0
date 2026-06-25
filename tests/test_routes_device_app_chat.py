"""Tests for routes/device_app_chat.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import device_app_chat as chat


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(chat.router)
    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def account():
    return {"id": "acc-1", "phone": "12345678901", "role": "user"}


@pytest.fixture(autouse=True)
def _patch_deps(account):
    with (
        patch.object(chat, "authorize", return_value=account),
        patch.object(chat, "connect") as mock_connect,
        patch.object(chat, "require_device_access", return_value=None),
    ):
        conn = MagicMock()
        # get_chat_messages checks that the session row belongs to the device.
        conn.execute.return_value.fetchone.return_value = {"device_id": "dev-1"}
        mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield


def test_list_chat_sessions_success(client, auth_header):
    response = client.get("/device/v1/app/devices/dev-1/chat-sessions", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["sessions"] == []


def test_get_chat_messages_success(client, auth_header):
    response = client.get("/device/v1/app/devices/dev-1/chat-sessions/s1/messages", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_list_chat_history_success(client, auth_header):
    response = client.get("/device/v1/app/devices/dev-1/chat-history", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["chatHistory"] == []


def test_get_audio_info_success(client, auth_header):
    with (
        patch("routes.upload._safe_upload_path", return_value=Path("/tmp/audio.wav")),
        patch("routes.upload_tokens.upload_access_token", return_value="tok-abc"),
    ):
        response = client.get("/device/v1/app/devices/dev-1/audio/aid-1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["audioId"] == "aid-1"
    assert "tok-abc" in response.json()["url"]


def test_get_audio_info_missing_audio_id(client, auth_header):
    response = client.get("/device/v1/app/devices/dev-1/audio/", headers=auth_header)
    assert response.status_code == 404


def test_get_audio_info_not_found(client, auth_header):
    with patch("routes.upload._safe_upload_path", return_value=None):
        response = client.get("/device/v1/app/devices/dev-1/audio/aid-1", headers=auth_header)
    assert response.status_code == 404


def test_routes_require_auth(client):
    with patch.object(chat, "authorize", return_value=chat.err(401, "Unauthorized", 401)):
        response = client.get("/device/v1/app/devices/dev-1/chat-sessions")
    assert response.status_code == 401
