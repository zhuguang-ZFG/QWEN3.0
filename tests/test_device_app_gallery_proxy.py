"""Proxy/token tests for routes.device_app_gallery."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from integrations.telegram_bot.client import TelegramNotConfiguredError
from tests.gallery_routes_helpers import (
    gallery_headers,
    gallery_token,
    mock_gallery_backend,
    seed_gallery_account,
    upload_gallery_jpeg,
)


def test_get_thumb_proxy_returns_bytes(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_backend = mock_gallery_backend(monkeypatch)
    mock_backend.download_file = AsyncMock(return_value=b"thumb-bytes")

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb", headers=gallery_headers("owner"))
    assert response.status_code == 200
    assert response.content == b"thumb-bytes"
    assert response.headers["content-type"].startswith("image/")
    assert "max-age=3600" in response.headers.get("cache-control", "")


def test_get_thumb_proxy_accepts_access_token_query(
    gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]
    token = gallery_token("owner")

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?access_token={token}")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store, private"


def test_get_thumb_proxy_accepts_thumb_token(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_backend = mock_gallery_backend(monkeypatch)
    mock_backend.get_file_url = AsyncMock(return_value="https://api.telegram.org/file/botsecret/thumbs/x.jpg")
    mock_backend.download_file = AsyncMock(return_value=b"thumb-bytes")

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]
    thumb_token = image["thumbToken"]
    assert thumb_token

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?thumb_token={thumb_token}")
    assert response.status_code == 200
    assert response.content == b"thumb-bytes"
    assert "max-age=3600" in response.headers.get("cache-control", "")


def test_get_thumb_proxy_rejects_fetch_token(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    download = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=gallery_headers("owner"))
    fetch_token = download.json()["data"]["url"].split("fetch_token=", 1)[1]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?fetch_token={fetch_token}")
    assert response.status_code == 401


def test_get_thumb_proxy_rejects_invalid_thumb_token(
    gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?thumb_token=bad:token")
    assert response.status_code == 401


def test_list_gallery_includes_thumb_token(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)
    upload_gallery_jpeg(gallery_client)

    response = gallery_client.get("/device/v1/app/gallery", headers=gallery_headers("owner"))
    images = response.json()["data"]["images"]
    assert len(images) == 1
    assert images[0]["thumbToken"]


def test_get_file_proxy_returns_bytes(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/file", headers=gallery_headers("owner"))
    assert response.status_code == 200
    assert response.content == b"fake-image-bytes"
    assert response.headers.get("cache-control") == "no-store, private"


def test_get_download_url_returns_stable_proxy(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_backend = mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    mock_backend.get_file_url.reset_mock()
    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=gallery_headers("owner"))
    assert response.status_code == 200
    url = response.json()["data"]["url"]
    assert f"/device/v1/app/gallery/{image_id}/file" in url
    assert "fetch_token=" in url
    assert "api.telegram.org" not in url
    mock_backend.get_file_url.assert_not_called()


def test_get_file_proxy_accepts_fetch_token(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    download = gallery_client.get(f"/device/v1/app/gallery/{image_id}/download", headers=gallery_headers("owner"))
    file_url = download.json()["data"]["url"]
    fetch_token = file_url.split("fetch_token=", 1)[1]

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/file?fetch_token={fetch_token}")
    assert response.status_code == 200
    assert response.content == b"fake-image-bytes"
    assert response.headers.get("cache-control") == "no-store, private"


def test_deleted_image_proxy_returns_404(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]
    thumb_token = image["thumbToken"]

    deleted = gallery_client.delete(f"/device/v1/app/gallery/{image_id}", headers=gallery_headers("owner"))
    assert deleted.status_code == 200

    response = gallery_client.get(f"/device/v1/app/gallery/{image_id}/thumb?thumb_token={thumb_token}")
    assert response.status_code == 404


def test_gallery_not_configured_returns_503(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")

    def _raise_missing() -> None:
        raise TelegramNotConfiguredError("missing")

    monkeypatch.setattr("routes.device_app_gallery.get_gallery_backend", _raise_missing)

    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=gallery_headers("owner"),
        files={"file": ("test.jpg", io.BytesIO(b"fake-image"), "image/jpeg")},
    )
    assert response.status_code == 503
