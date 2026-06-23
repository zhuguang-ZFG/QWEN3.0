"""Tests for routes/admin_api_extra.py."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_api_extra


def test_router_import_and_include():
    app = FastAPI()
    app.include_router(admin_api_extra.router)
    assert any(r.path == "/api/backends/{name}" for r in app.routes)
    assert any(r.path == "/api/logs/stream" for r in app.routes)


def test_broadcast_log_exported():
    assert callable(admin_api_extra.broadcast_log)
