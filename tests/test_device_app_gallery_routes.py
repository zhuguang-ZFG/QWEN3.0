"""Tests for routes.device_app_gallery."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect
from routes.device_app_gallery import router as gallery_router


def _token(account_id: str) -> str:
    import time

    now = int(time.time())
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")


def _headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(account_id)}"}


def _seed_account(account_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            (account_id, f"{account_id}-phone", account_id),
        )
        conn.commit()


@pytest.fixture
def gallery_client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "gallery_routes.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_GALLERY_CHAT_ID", "456")
    _schema_ready_paths.clear()
    reset_activation_store_for_tests()
    reset_tasks_for_tests()
    install_task_store_for_tests(InMemoryDeviceTaskStore())

    app = FastAPI()
    app.include_router(gallery_router)
    return TestClient(app)


def test_list_gallery_requires_auth(gallery_client: TestClient) -> None:
    response = gallery_client.get("/device/v1/app/gallery")
    assert response.status_code == 401


def test_list_gallery_empty(gallery_client: TestClient) -> None:
    _seed_account("owner")
    response = gallery_client.get("/device/v1/app/gallery", headers=_headers("owner"))
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["images"] == []


def test_upload_gallery_image_success(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")

    mock_client = AsyncMock()
    mock_client.send_photo = AsyncMock(return_value="telegram-file-id")
    mock_client.get_file_url = AsyncMock(return_value="https://t.me/file.jpg")

    monkeypatch.setattr("routes.device_app_gallery.TelegramBotClient", lambda: mock_client)

    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["fileId"] == "telegram-file-id"
    assert data["data"]["thumbUrl"] == "https://t.me/file.jpg"

    listed = gallery_client.get("/device/v1/app/gallery", headers=_headers("owner"))
    assert listed.json()["data"]["count"] == 1


def test_upload_gallery_unsupported_type(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 400


def test_delete_gallery_image(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")

    mock_client = AsyncMock()
    mock_client.send_photo = AsyncMock(return_value="file-to-delete")
    mock_client.get_file_url = AsyncMock(return_value="https://t.me/file.jpg")
    monkeypatch.setattr("routes.device_app_gallery.TelegramBotClient", lambda: mock_client)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    deleted = gallery_client.delete(f"/device/v1/app/gallery/{image_id}", headers=_headers("owner"))
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    listed = gallery_client.get("/device/v1/app/gallery", headers=_headers("owner"))
    assert listed.json()["data"]["count"] == 0


def test_get_download_url_refreshes(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")

    mock_client = AsyncMock()
    mock_client.send_photo = AsyncMock(return_value="file-download")
    mock_client.get_file_url = AsyncMock(return_value="https://t.me/old.jpg")
    monkeypatch.setattr("routes.device_app_gallery.TelegramBotClient", lambda: mock_client)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    mock_client.get_file_url = AsyncMock(return_value="https://t.me/fresh.jpg")
    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=_headers("owner"))
    assert response.status_code == 200
    assert response.json()["data"]["url"] == "https://t.me/fresh.jpg"


def test_gallery_not_configured_returns_503(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 503
