"""Tests for routes.device_app_gallery."""

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
from integrations.telegram_bot.client import TelegramNotConfiguredError
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


def _mock_backend(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock_backend = AsyncMock()
    mock_backend.send_photo = AsyncMock(return_value="telegram-file-id")
    mock_backend.get_file_url = AsyncMock(return_value="https://api.telegram.org/file/botsecret/photos/x.jpg")
    mock_backend.download_file = AsyncMock(return_value=b"fake-image-bytes")
    monkeypatch.setattr("routes.device_app_gallery.get_gallery_backend", lambda: mock_backend)
    return mock_backend


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
    _mock_backend(monkeypatch)

    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["fileId"] == "telegram-file-id"
    assert data["data"]["thumbUrl"].endswith(f"/device/v1/app/gallery/{data['data']['id']}/thumb")
    assert data["data"]["fileUrl"].endswith(f"/device/v1/app/gallery/{data['data']['id']}/file")

    listed = gallery_client.get("/device/v1/app/gallery", headers=_headers("owner"))
    assert listed.json()["data"]["count"] == 1


def test_upload_gallery_unsupported_type(gallery_client: TestClient) -> None:
    _seed_account("owner")
    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 400


def test_delete_gallery_image(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    _mock_backend(monkeypatch)

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


def test_list_gallery_does_not_hit_telegram(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    mock_backend = _mock_backend(monkeypatch)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]
    mock_backend.get_file_url.reset_mock()

    response = gallery_client.get("/device/v1/app/gallery", headers=_headers("owner"))
    assert response.status_code == 200
    image = response.json()["data"]["images"][0]
    assert image["thumbUrl"].endswith(f"/device/v1/app/gallery/{image_id}/thumb")
    mock_backend.get_file_url.assert_not_called()


def test_get_thumb_proxy_returns_bytes(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    mock_backend = _mock_backend(monkeypatch)
    mock_backend.download_file = AsyncMock(return_value=b"thumb-bytes")

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb", headers=_headers("owner"))
    assert response.status_code == 200
    assert response.content == b"thumb-bytes"
    assert response.headers["content-type"].startswith("image/")
    assert "max-age=3600" in response.headers.get("cache-control", "")


def test_get_thumb_proxy_accepts_access_token_query(
    gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_account("owner")
    _mock_backend(monkeypatch)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]
    token = _token("owner")

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?access_token={token}")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store, private"


def test_get_file_proxy_returns_bytes(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    _mock_backend(monkeypatch)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/file", headers=_headers("owner"))
    assert response.status_code == 200
    assert response.content == b"fake-image-bytes"
    assert response.headers.get("cache-control") == "no-store, private"


def test_get_download_url_returns_stable_proxy(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    mock_backend = _mock_backend(monkeypatch)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    mock_backend.get_file_url.reset_mock()
    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=_headers("owner"))
    assert response.status_code == 200
    url = response.json()["data"]["url"]
    assert f"/device/v1/app/gallery/{image_id}/file" in url
    assert "fetch_token=" in url
    assert "api.telegram.org" not in url
    mock_backend.get_file_url.assert_not_called()


def test_get_file_proxy_accepts_fetch_token(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")
    _mock_backend(monkeypatch)

    upload = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    image_id = upload.json()["data"]["id"]

    download = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=_headers("owner"))
    file_url = download.json()["data"]["url"]
    fetch_token = file_url.split("fetch_token=", 1)[1]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/file?fetch_token={fetch_token}")
    assert response.status_code == 200
    assert response.content == b"fake-image-bytes"
    assert response.headers.get("cache-control") == "no-store, private"


def test_gallery_not_configured_returns_503(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_account("owner")

    def _raise_missing() -> None:
        raise TelegramNotConfiguredError("missing")

    monkeypatch.setattr("routes.device_app_gallery.get_gallery_backend", _raise_missing)

    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 503
