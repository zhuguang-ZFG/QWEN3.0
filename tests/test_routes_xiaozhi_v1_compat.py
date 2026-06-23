"""Tests for routes/xiaozhi_v1_compat.py."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import xiaozhi_v1_compat as xz


def test_router_has_routes():
    assert len(xz.router.routes) > 0


def test_router_includes_sub_routers():
    paths = {r.path for r in xz.router.routes}
    # Each sub-router should add at least one route.
    assert paths
    assert any("/api/v1" in p for p in paths)


def test_mount_in_app():
    app = FastAPI()
    app.include_router(xz.router)
    client = TestClient(app)
    # Health/unknown path returns 404 but router is mounted.
    response = client.get("/api/v1/health")
    assert response.status_code == 404


def test_backward_compat_exports():
    assert callable(xz._connect)
    assert xz._schema_ready_paths is not None
    assert xz.jwt is not None
