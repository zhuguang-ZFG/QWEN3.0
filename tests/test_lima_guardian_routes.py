"""Tests for scripts/lima_guardian route registration detection."""

from __future__ import annotations

from fastapi.routing import APIRoute

import server
from scripts.guardian_test_index import find_test_file
from scripts.lima_guardian import CodeScanner, _check_route_registration


def test_prometheus_route_is_mounted_on_server():
    paths = {route.path for route in server.app.routes if isinstance(route, APIRoute)}
    assert "/v1/ops/metrics/prometheus" in paths


def test_guardian_recognizes_nested_ops_metrics_prometheus_router():
    status = _check_route_registration("routes/ops_metrics/prometheus.py")
    assert status == "routes.ops_metrics.prometheus"


def test_guardian_flags_truly_unregistered_route_file(tmp_path, monkeypatch):
    orphan = tmp_path / "routes" / "orphan_module.py"
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n"
        '@router.get("/orphan")\ndef orphan_route():\n    return {"ok": True}\n',
        encoding="utf-8",
    )
    findings = CodeScanner.scan_file(orphan)
    types = {f["type"] for f in findings}
    assert "route_unregistered" in types


def test_find_test_file_recognizes_ops_metrics_package_import():
    hit = find_test_file("routes/ops_metrics/prometheus.py")
    assert hit is not None
    assert "ops_metrics" in hit.replace("\\", "/")


def test_find_test_file_recognizes_routes_auth_contract():
    hit = find_test_file("routes/health_dashboard.py")
    assert hit is not None
    assert "health_dashboard" in hit.replace("\\", "/")


def test_find_test_file_recognizes_module_specific_admin_tests():
    hit = find_test_file("routes/admin_api.py")
    assert hit is not None
    assert "admin" in hit.replace("\\", "/")
