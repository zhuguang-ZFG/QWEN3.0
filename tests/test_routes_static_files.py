"""Tests for routes/static_files.py."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import static_files as sf


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "_BASE_DIR", tmp_path)
    (tmp_path / "data" / "chat").mkdir(parents=True)
    (tmp_path / "donglicao-site").mkdir(parents=True)
    app = FastAPI()
    app.include_router(sf.router)
    return TestClient(app)


def _write(tmp_path, rel, content="x"):
    path = tmp_path / rel
    path.write_text(content, encoding="utf-8")
    return path


def test_serve_service_worker(client, tmp_path):
    _write(tmp_path, "data/chat/sw.js", "self.addEventListener")
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "no-cache" in response.headers["cache-control"]


def test_serve_service_worker_missing(client):
    response = client.get("/sw.js")
    assert response.status_code == 404


def test_serve_manifest(client, tmp_path):
    _write(tmp_path, "data/chat/manifest.json", '{"name":"LiMa"}')
    response = client.get("/manifest.json")
    assert response.status_code == 200
    assert response.json()["name"] == "LiMa"


def test_serve_index_donglicao_site(client, tmp_path):
    _write(tmp_path, "donglicao-site/chat.html", "<html>chat</html>")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<html>chat</html>"


def test_serve_index_data_fallback(client, tmp_path):
    _write(tmp_path, "data/chat/index.html", "<html>index</html>")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "<html>index</html>"


def test_serve_index_missing(client):
    response = client.get("/")
    assert response.status_code == 404


def test_serve_admin_css(client, tmp_path):
    _write(tmp_path, "data/chat/admin.css", "body{}")
    response = client.get("/chat/admin.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]


def test_serve_admin_js(client, tmp_path):
    _write(tmp_path, "data/chat/admin.js", "console.log()")
    response = client.get("/chat/admin.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
