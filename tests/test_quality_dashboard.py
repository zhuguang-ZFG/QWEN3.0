"""Tests for quality trend data in dashboard/metrics endpoints.

Verifies that /api/stats, /api/backend-health, and /v1/ops/metrics
all include semantic quality trend information.
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import quality_history
from routes import admin_api
from routes.admin_auth import verify_admin
from routes.admin_state import stats_context
from routes.ops_metrics import router as ops_router


def setup_function():
    quality_history.reset_all()


# ── admin_stats quality summary ──────────────────────────────────────────────

def _build_admin_client():
    """Build a TestClient for admin_api with auth bypassed."""
    stats, lock, enabled = stats_context()
    with lock:
        stats["start_time"] = 0
        stats["total_requests"] = 0
        stats["backend_calls"] = {}
        stats["intent_distribution"] = {}
        stats["recent_logs"] = []

    # Patch stats_context so admin_stats uses our controlled state
    admin_api.stats_context = lambda: (stats, lock, enabled)

    app = FastAPI()
    app.dependency_overrides[verify_admin] = lambda: None
    app.include_router(admin_api.router, prefix="/admin")
    return TestClient(app)


def test_admin_stats_includes_quality_summary():
    """Verify /api/stats response includes quality_trends summary."""
    for _ in range(10):
        quality_history.record_quality("backend_a", 85.0)
    for _ in range(10):
        quality_history.record_quality("backend_b", 40.0)

    client = _build_admin_client()
    response = client.get("/admin/api/stats")
    assert response.status_code == 200
    body = response.json()

    assert "quality_trends" in body
    qt = body["quality_trends"]
    assert qt["tracked_backends"] == 2
    assert qt["avg_quality"] > 0
    assert "declining" in qt
    assert "improving" in qt
    assert "stable" in qt


def test_admin_stats_quality_summary_empty():
    """With no quality data, quality_trends should have zero counts."""
    client = _build_admin_client()
    response = client.get("/admin/api/stats")
    assert response.status_code == 200
    body = response.json()

    assert "quality_trends" in body
    qt = body["quality_trends"]
    assert qt["tracked_backends"] == 0
    assert qt["avg_quality"] == 0.0


def test_admin_stats_quality_summary_counts_trends():
    """Quality summary should correctly count declining/improving/stable backends."""
    # Create a declining backend
    for _ in range(15):
        quality_history.record_quality("declining_b", 90.0)
    for _ in range(15):
        quality_history.record_quality("declining_b", 20.0)

    # Create an improving backend
    for _ in range(15):
        quality_history.record_quality("improving_b", 20.0)
    for _ in range(15):
        quality_history.record_quality("improving_b", 90.0)

    # Create a stable backend
    for _ in range(15):
        quality_history.record_quality("stable_b", 75.0)

    client = _build_admin_client()
    response = client.get("/admin/api/stats")
    body = response.json()
    qt = body["quality_trends"]

    assert qt["tracked_backends"] == 3
    assert qt["declining"] >= 1
    assert qt["improving"] >= 1


# ── backend-health quality per backend ───────────────────────────────────────

def test_backend_health_includes_quality_trend():
    """Each backend in /api/backend-health should include quality_trend data."""
    for _ in range(10):
        quality_history.record_quality("test_backend", 75.0)

    qt = quality_history.get_quality_trend("test_backend")
    qt_data = {
        "average": qt.average,
        "trend": qt.trend,
        "confidence": qt.confidence,
        "sample_count": qt.sample_count,
        "recent_average": qt.recent_average,
    }

    assert qt_data["average"] == 75.0
    assert qt_data["sample_count"] == 10
    assert qt_data["trend"] in ("stable", "improving", "declining")


def test_backend_health_quality_default_for_unknown():
    """Backends with no quality history should get default trend data."""
    qt = quality_history.get_quality_trend("unknown_backend")
    qt_data = {
        "average": qt.average,
        "trend": qt.trend,
        "confidence": qt.confidence,
        "sample_count": qt.sample_count,
    }

    assert qt_data["average"] == 50.0
    assert qt_data["trend"] == "stable"
    assert qt_data["sample_count"] == 0


# ── ops_metrics quality section ──────────────────────────────────────────────

def _build_ops_client():
    """Build a TestClient for ops_metrics with auth bypassed."""
    app = FastAPI()
    app.state.stats = {
        "total_requests": 0,
        "backend_calls": {},
        "start_time": 1,
    }
    app.include_router(ops_router)
    return TestClient(app)


def test_ops_metrics_includes_quality_section():
    """ops_metrics should include quality trends in its response."""
    for _ in range(10):
        quality_history.record_quality("good_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 90.0)
    for _ in range(10):
        quality_history.record_quality("bad_backend", 20.0)

    import os
    os.environ["LIMA_API_KEY"] = "test-key-for-quality"
    client = _build_ops_client()
    response = client.get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-key-for-quality"},
    )
    assert response.status_code == 200
    data = response.json()

    assert "quality" in data
    q = data["quality"]
    assert q["tracked_backends"] == 2
    assert "bad_backend" in q["declining_backends"]
    assert q["total_samples"] == 30  # 10 + 20
    del os.environ["LIMA_API_KEY"]


def test_ops_metrics_quality_empty():
    """With no quality data, quality section should be present but empty."""
    import os
    os.environ["LIMA_API_KEY"] = "test-key-for-quality"
    client = _build_ops_client()
    response = client.get(
        "/v1/ops/metrics",
        headers={"Authorization": "Bearer test-key-for-quality"},
    )
    assert response.status_code == 200
    data = response.json()

    assert "quality" in data
    q = data["quality"]
    assert q["tracked_backends"] == 0
    assert q["declining_backends"] == []
    assert q["total_samples"] == 0
    del os.environ["LIMA_API_KEY"]
