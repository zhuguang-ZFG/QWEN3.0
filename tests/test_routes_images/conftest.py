"""Shared fixtures for routes/images tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import images as img
from routes import images_cache as image_cache
from routes import images_pollinations as pollinations


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    monkeypatch.setenv("LIMA_API_KEY", "test-key")
    img._record_request_fn = None
    image_cache.clear_cache()
    pollinations._PROMPT_TRANSLATE_ENABLED = False


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(img.router)
    return TestClient(app)


def auth_header():
    return {"Authorization": "Bearer test-key"}
