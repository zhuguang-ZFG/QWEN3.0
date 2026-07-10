"""Shared fixtures for device_app_gallery route tests."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from device_gateway.gallery_service import clear_proxy_cache_for_tests
from device_gateway.store import InMemoryDeviceTaskStore
from device_gateway.tasks import install_task_store_for_tests, reset_tasks_for_tests
from device_logic.activation import reset_activation_store_for_tests
from device_logic.auth import jwt
from device_logic.db import _schema_ready_paths, connect
from routes.device_app_gallery import router as gallery_router


def gallery_token(account_id: str) -> str:
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


def gallery_headers(account_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {gallery_token(account_id)}"}


def seed_gallery_account(account_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)",
            (account_id, f"{account_id}-phone", account_id),
        )
        conn.commit()


def mock_gallery_backend(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock_backend = AsyncMock()
    mock_backend.send_photo = AsyncMock(return_value="telegram-file-id")
    mock_backend.get_file_url = AsyncMock(return_value="https://api.telegram.org/file/botsecret/photos/x.jpg")
    mock_backend.download_file = AsyncMock(return_value=b"fake-image-bytes")
    monkeypatch.setattr("routes.device_app_gallery.get_gallery_backend", lambda: mock_backend)
    return mock_backend


def upload_gallery_jpeg(client: TestClient, account_id: str = "owner") -> dict:
    response = client.post(
        "/device/v1/app/gallery",
        headers=gallery_headers(account_id),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


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
    clear_proxy_cache_for_tests()

    app = FastAPI()
    app.include_router(gallery_router)
    return TestClient(app)
