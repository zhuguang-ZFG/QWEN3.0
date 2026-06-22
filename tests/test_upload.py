"""Tests for the /upload endpoint and /uploads static serving."""

from __future__ import annotations

import io
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.upload import router as upload_router, serve_uploaded_file
from routes.xiaozhi_compat.auth import jwt
from device_logic.db import connect


def _auth_headers(account_id: str = "a-upload") -> dict[str, str]:
    payload = {
        "sub": account_id,
        "account_id": account_id,
        "role": "user",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    token = jwt.encode(payload, "test-secret-minimum-32-bytes-long!!", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _png_bytes(payload: bytes = b"fake-png-data") -> bytes:
    return b"\x89PNG\r\n\x1a\n" + payload


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_DB_PATH", str(tmp_path / "upload.db"))
    monkeypatch.setenv("LIMA_JWT_SECRET", "test-secret-minimum-32-bytes-long!!")

    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)", ("a-upload", "13010", "uploader"))
        conn.commit()

    app = FastAPI()
    app.include_router(upload_router)
    return TestClient(app)


def test_upload_requires_auth(upload_client):
    response = upload_client.post("/upload", files={"file": ("test.png", io.BytesIO(_png_bytes()), "image/png")})
    assert response.status_code == 401


def test_upload_rejects_disallowed_type(upload_client):
    response = upload_client.post(
        "/upload",
        files={"file": ("test.exe", io.BytesIO(b"fake"), "application/octet-stream")},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert "file type not allowed" in response.json()["message"]


def test_upload_rejects_fake_image_content(upload_client):
    response = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(b"not-a-real-image"), "image/png")},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert "file content does not match image type" in response.json()["message"]


def test_upload_rejects_oversized_file(upload_client, monkeypatch):
    monkeypatch.setattr("routes.upload._MAX_SIZE_BYTES", 10)
    response = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(_png_bytes(b"0123456789extra")), "image/png")},
        headers=_auth_headers(),
    )
    assert response.status_code == 413
    assert "file size exceeds" in response.json()["message"]


def test_upload_image_and_serve_it_back(upload_client):
    image_bytes = _png_bytes()
    response = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(image_bytes), "image/png")},
        headers=_auth_headers(),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["url"].startswith("http://testserver/uploads/")
    assert "token=" in data["data"]["url"]
    assert data["data"]["token"]
    assert data["data"]["size"] == len(image_bytes)

    filename = data["data"]["name"]
    token = data["data"]["token"]
    get_response = upload_client.get(f"/uploads/{filename}?token={token}")
    assert get_response.status_code == 200
    assert get_response.content == image_bytes
    assert get_response.headers["content-type"] == "image/png"


def test_serve_upload_requires_token_or_auth(upload_client):
    image_bytes = _png_bytes()
    response = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(image_bytes), "image/png")},
        headers=_auth_headers(),
    )
    filename = response.json()["data"]["name"]
    denied = upload_client.get(f"/uploads/{filename}")
    assert denied.status_code == 401

    allowed = upload_client.get(f"/uploads/{filename}", headers=_auth_headers())
    assert allowed.status_code == 200


def test_serve_upload_public_get_env(upload_client, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", "1")
    image_bytes = _png_bytes()
    response = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(image_bytes), "image/png")},
        headers=_auth_headers(),
    )
    filename = response.json()["data"]["name"]
    get_response = upload_client.get(f"/uploads/{filename}")
    assert get_response.status_code == 200


def test_upload_missing_file_returns_422(upload_client):
    response = upload_client.post("/upload", headers=_auth_headers())
    assert response.status_code == 422


def test_serve_missing_upload_returns_404(upload_client):
    response = upload_client.get("/uploads/does-not-exist.png")
    assert response.status_code == 404


@pytest.mark.parametrize("filename", ["../../server.py", "..%2F..%2Fserver.py", "not-uuid.png"])
def test_serve_rejects_unsafe_or_unknown_filename(upload_client, filename):
    response = upload_client.get(f"/uploads/{filename}")
    assert response.status_code == 404


def test_upload_rate_limited_per_account(upload_client, monkeypatch):
    monkeypatch.setattr("routes.upload._UPLOAD_MAX_PER_MIN", 1)
    import rate_limiter

    rate_limiter.reset()

    first = upload_client.post(
        "/upload",
        files={"file": ("test.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=_auth_headers(),
    )
    assert first.status_code == 200, first.text

    blocked = upload_client.post(
        "/upload",
        files={"file": ("test2.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=_auth_headers(),
    )
    assert blocked.status_code == 429
    assert "rate_limit_error" in blocked.json()["error"]["type"]

    # A different account should still be allowed.
    with connect() as conn:
        conn.execute("INSERT INTO v2_account (id, phone, nickname) VALUES (?, ?, ?)", ("a-upload-2", "13011", "uploader2"))
        conn.commit()
    allowed = upload_client.post(
        "/upload",
        files={"file": ("test3.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=_auth_headers("a-upload-2"),
    )
    assert allowed.status_code == 200, allowed.text


@pytest.mark.asyncio
async def test_serve_uploaded_file_blocks_path_traversal():
    response = await serve_uploaded_file("../../server.py")
    assert response.status_code == 404
