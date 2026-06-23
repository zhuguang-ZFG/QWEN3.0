"""Tests for routes/health_dashboard.py pure helpers."""

from __future__ import annotations

import time

from routes.health_dashboard import (
    _build_backend_row,
    _build_dashboard_html,
    _health_badge,
    _render_dashboard,
)


class TestHealthBadge:
    def test_known_statuses(self):
        assert _health_badge("healthy") == ("#22c55e", "Healthy")
        assert _health_badge("degraded") == ("#eab308", "Degraded")
        assert _health_badge("dead") == ("#ef4444", "Dead")

    def test_unknown_status(self):
        assert _health_badge("unknown") == ("#6b7280", "Unknown")


class TestBuildBackendRow:
    def test_contains_all_cells(self):
        backend = {
            "name": "groq",
            "health": "healthy",
            "score": 95.5,
            "avg_latency_ms": 12.3,
            "total_requests": 42,
            "cooldown_remaining_s": 0,
            "last_error_code": None,
            "last_error_class": None,
            "caps": ["chat", "fast"],
            "budget": "ok",
        }
        row = _build_backend_row(backend)
        assert "groq" in row
        assert "Healthy" in row
        assert "95" in row or "96" in row
        assert "12" in row
        assert "chat" in row
        assert "ok" in row

    def test_cooldown_rendered(self):
        backend = {
            "name": "slow",
            "health": "degraded",
            "score": 50,
            "avg_latency_ms": 100,
            "total_requests": 1,
            "cooldown_remaining_s": 30,
            "last_error_code": 503,
            "last_error_class": None,
            "caps": [],
            "budget": "low",
        }
        row = _build_backend_row(backend)
        assert "30s" in row
        assert "HTTP 503" in row


class TestBuildDashboardHtml:
    def test_structure_and_counts(self):
        data = {
            "healthy": 2,
            "degraded": 1,
            "dead": 0,
            "cooled": 1,
            "total": 3,
        }
        html = _build_dashboard_html(data, "now", ["<tr>row</tr>"])
        assert html.startswith("<!DOCTYPE html>")
        assert "LiMa Backend Health Dashboard" in html
        assert 'http-equiv="refresh" content="30"' in html
        assert "row" in html


class TestRenderDashboard:
    def test_sorts_by_score_desc(self):
        base_backend = {
            "health": "healthy",
            "avg_latency_ms": 0,
            "total_requests": 0,
            "cooldown_remaining_s": 0,
            "last_error_code": None,
            "last_error_class": None,
            "caps": [],
            "budget": "ok",
        }
        data = {
            "timestamp": time.time(),
            "healthy": 3,
            "degraded": 0,
            "dead": 0,
            "cooled": 0,
            "total": 3,
            "backends": [
                {**base_backend, "name": "low", "score": 10},
                {**base_backend, "name": "high", "score": 90},
                {**base_backend, "name": "mid", "score": 50},
            ],
        }
        html = _render_dashboard(data)
        high_pos = html.find("high</td>")
        mid_pos = html.find("mid</td>")
        low_pos = html.find("low</td>")
        assert high_pos < mid_pos < low_pos

    def test_includes_timestamp(self):
        ts = time.time()
        html = _render_dashboard(
            {
                "timestamp": ts,
                "healthy": 0,
                "degraded": 0,
                "dead": 0,
                "cooled": 0,
                "total": 0,
                "backends": [],
            }
        )
        assert "Last updated:" in html
