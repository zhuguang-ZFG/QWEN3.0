"""Tests for routes/upload.py."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import upload as up
from routes import upload_tokens


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"data"


def _valid_filename(ext: str = "png") -> str:
    return f"{'a' * 32}.{ext}"


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    monkeypatch.setenv("LIMA_JWT_SECRET", "jwt-secret")
    monkeypatch.setattr(up, "_UPLOAD_DIR", tmp_path)

    def _fake_authorize(authorization: str):
        if authorization and "Bearer" in authorization:
            return {"id": "account-1"}
        return up.JSONResponse({"code": 401, "message": "Unauthorized"}, status_code=401)

    monkeypatch.setattr(up, "authorize", _fake_authorize)
    monkeypatch.setattr(up, "check_key_limit", MagicMock(return_value=None))


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(up.router)
    return TestClient(app)


def test_upload_requires_auth(client):
    response = client.post("/upload", files={"file": ("test.png", BytesIO(_png_bytes()), "image/png")})
    assert response.status_code == 401


def test_upload_rate_limit(client, monkeypatch):
    monkeypatch.setattr(
        up,
        "check_key_limit",
        MagicMock(return_value=up.JSONResponse({"error": "rate limit"}, status_code=429)),
    )
    response = client.post(
        "/upload",
        files={"file": ("test.png", BytesIO(_png_bytes()), "image/png")},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 429


def test_upload_rejects_non_image(client):
    response = client.post(
        "/upload",
        files={"file": ("test.txt", BytesIO(b"text"), "text/plain")},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400


def test_upload_rejects_oversize(client, monkeypatch):
    monkeypatch.setattr(up, "_MAX_SIZE_BYTES", 10)
    response = client.post(
        "/upload",
        files={"file": ("test.png", BytesIO(_png_bytes()), "image/png")},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 413


def test_upload_rejects_bad_signature(client):
    response = client.post(
        "/upload",
        files={"file": ("test.png", BytesIO(b"not an image"), "image/png")},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 400
    assert "content does not match" in response.json()["message"]


def test_upload_success(client):
    response = client.post(
        "/upload",
        files={"file": ("test.png", BytesIO(_png_bytes()), "image/png")},
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert "uploads/" in payload["data"]["url"]
    assert payload["data"]["name"].endswith(".png")


def test_serve_uploaded_file_requires_token(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", "0")
    filename = _valid_filename()
    stored = tmp_path / filename
    stored.write_bytes(_png_bytes())
    monkeypatch.setattr(up, "_UPLOAD_DIR", tmp_path)
    response = client.get(f"/uploads/{filename}")
    assert response.status_code == 401


def test_serve_uploaded_file_with_valid_token(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_TOKEN_SECRET", "secret")
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", "0")
    filename = _valid_filename()
    stored = tmp_path / filename
    stored.write_bytes(_png_bytes())
    monkeypatch.setattr(up, "_UPLOAD_DIR", tmp_path)
    token = upload_tokens.upload_access_token(filename, ttl_seconds=3600)
    response = client.get(f"/uploads/{filename}?token={token}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_serve_uploaded_file_public_get(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", "1")
    filename = _valid_filename()
    stored = tmp_path / filename
    stored.write_bytes(_png_bytes())
    monkeypatch.setattr(up, "_UPLOAD_DIR", tmp_path)
    response = client.get(f"/uploads/{filename}")
    assert response.status_code == 200


def test_serve_missing_file_returns_404(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_UPLOAD_PUBLIC_GET", "1")
    monkeypatch.setattr(up, "_UPLOAD_DIR", tmp_path)
    response = client.get(f"/uploads/{_valid_filename()}")
    assert response.status_code == 404


def test_serve_invalid_filename_returns_404(client):
    response = client.get("/uploads/../foo.png")
    assert response.status_code == 404
