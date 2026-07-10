"""CRUD/list tests for routes.device_app_gallery."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from tests.gallery_routes_helpers import (
    gallery_headers,
    mock_gallery_backend,
    seed_gallery_account,
    upload_gallery_jpeg,
)


def test_list_gallery_requires_auth(gallery_client: TestClient) -> None:
    response = gallery_client.get("/device/v1/app/gallery")
    assert response.status_code == 401


def test_list_gallery_empty(gallery_client: TestClient) -> None:
    seed_gallery_account("owner")
    response = gallery_client.get("/device/v1/app/gallery", headers=gallery_headers("owner"))
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["images"] == []
    assert data["data"]["total"] == 0


def test_upload_gallery_image_success(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    data = upload_gallery_jpeg(gallery_client)
    assert data["fileId"] == "telegram-file-id"
    assert data["thumbUrl"].endswith(f"/device/v1/app/gallery/{data['id']}/thumb")
    assert data["fileUrl"].endswith(f"/device/v1/app/gallery/{data['id']}/file")
    assert data["thumbToken"]

    listed = gallery_client.get("/device/v1/app/gallery", headers=gallery_headers("owner"))
    listed_data = listed.json()["data"]
    assert listed_data["count"] == 1
    assert listed_data["total"] == 1


def test_upload_gallery_unsupported_type(gallery_client: TestClient) -> None:
    seed_gallery_account("owner")
    response = gallery_client.post(
        "/device/v1/app/gallery",
        headers=gallery_headers("owner"),
        files={"file": ("test.txt", io.BytesIO(b"text"), "text/plain")},
    )
    assert response.status_code == 400


def test_delete_gallery_image(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]

    deleted = gallery_client.delete(f"/device/v1/app/gallery/{image_id}", headers=gallery_headers("owner"))
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    listed = gallery_client.get("/device/v1/app/gallery", headers=gallery_headers("owner"))
    assert listed.json()["data"]["count"] == 0


def test_list_gallery_does_not_hit_telegram(gallery_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_gallery_account("owner")
    mock_backend = mock_gallery_backend(monkeypatch)

    image = upload_gallery_jpeg(gallery_client)
    image_id = image["id"]
    mock_backend.get_file_url.reset_mock()

    response = gallery_client.get("/device/v1/app/gallery", headers=gallery_headers("owner"))
    assert response.status_code == 200
    listed_image = response.json()["data"]["images"][0]
    assert listed_image["thumbUrl"].endswith(f"/device/v1/app/gallery/{image_id}/thumb")
    mock_backend.get_file_url.assert_not_called()
