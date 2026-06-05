"""Tests for backend health summary."""

from __future__ import annotations

import health_summary as mod


def test_summarize_backend_health_warmup_counts_unknown(monkeypatch):
    monkeypatch.setattr(mod, "get_health_map", lambda: {})
    monkeypatch.setattr(
        "backends_registry.BACKENDS",
        {"a": {}, "b": {}, "c": {}},
        raising=False,
    )
    summary = mod.summarize_backend_health()
    assert summary["total"] == 3
    assert summary["healthy"] == 0
    assert summary["unknown"] == 3
    assert summary["warmup"] is True


def test_format_backend_health_line_includes_warmup_note():
    line = mod.format_backend_health_line(
        {
            "total": 10,
            "tracked": 0,
            "warmup": True,
            "healthy": 0,
            "unknown": 10,
            "degraded": 0,
            "dead": 0,
        }
    )
    assert "10 total" in line
    assert "unprobed" in line
    assert "warmup" in line
