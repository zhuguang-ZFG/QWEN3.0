"""Tests for routes/digital_human.py."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import digital_human as dh


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    app = FastAPI()
    app.include_router(dh.router)
    return TestClient(app)


@pytest.fixture
def assets_available(tmp_path, monkeypatch):
    index = tmp_path / "index.html"
    index.write_text(
        '<html><head><title>小智数字人页面</title></head><body>'
        '<div class="brand">小智 AI 语音/视频通话</div>'
        '<script type="module" src="js/app.js?v=0205"></script></body></html>',
        encoding="utf-8",
    )
    (tmp_path / "style.css").write_text("body {}", encoding="utf-8")
    monkeypatch.setattr(dh, "_ASSETS_AVAILABLE", True)
    monkeypatch.setattr(dh, "_DH_DIR", tmp_path)
    monkeypatch.setattr(dh, "_INDEX_PATH", index)
    return tmp_path, index


@pytest.fixture
def assets_unavailable(monkeypatch):
    monkeypatch.setattr(dh, "_ASSETS_AVAILABLE", False)
    monkeypatch.setattr(dh, "_INDEX_PATH", dh._DEFAULT_DH_DIR / "index.html")


def test_health_when_unavailable(client, assets_unavailable):
    response = client.get("/digital-human/health")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


def test_index_unavailable_returns_404(client, assets_unavailable):
    response = client.get("/digital-human/")
    assert response.status_code == 404


def test_static_unavailable_returns_404(client, assets_unavailable):
    response = client.get("/digital-human/js/app.js")
    assert response.status_code == 404


def test_index_patched_content(client, assets_available):
    response = client.get("/digital-human/")
    assert response.status_code == 200
    text = response.text
    assert "LiMa 量子星云数字人页面" in text
    assert "LiMa 量子星云 AI 语音/视频通话" in text
    assert "limaWsUrl" in text
    assert "js/app.js?v=0205" in text


def test_static_file_served(client, assets_available):
    response = client.get("/digital-human/style.css")
    assert response.status_code == 200
    assert "body" in response.text


def test_static_path_traversal_blocked(client, assets_available):
    response = client.get("/digital-human/../package.json")
    assert response.status_code == 404


def test_static_missing_file_returns_404(client, assets_available):
    response = client.get("/digital-human/missing.png")
    assert response.status_code == 404


def test_build_auto_config_script():
    script = dh._build_auto_config_script(
        device_id="dev-1", device_name="Test", client_id="client-1", wakeword_enabled=True
    )
    assert "dev-1" in script
    assert "Test" in script
    assert "client-1" in script
    assert "wakewordEnabled" in script


def test_digital_human_defaults(monkeypatch):
    from config.settings import DIGITAL_HUMAN

    monkeypatch.setattr(DIGITAL_HUMAN, "device_id", "custom-id")
    defaults = dh._digital_human_defaults()
    assert defaults["device_id"] == "custom-id"
    assert defaults["wakeword_enabled"] is False


def test_mount_static_files_noop():
    # Should not raise and do nothing.
    dh.mount_static_files(None)
