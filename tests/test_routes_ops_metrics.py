"""Tests for routes/ops_metrics.py shim."""

from __future__ import annotations

from routes import ops_metrics


def test_router_exported():
    assert ops_metrics.router is not None
    assert hasattr(ops_metrics.router, "routes")
