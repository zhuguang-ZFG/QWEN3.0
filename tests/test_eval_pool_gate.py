"""Tests for eval-driven coding pool gate."""

from __future__ import annotations

import json
from pathlib import Path

import eval_pool_gate as mod


def test_demoted_backends_excludes_zero_avg(tmp_path: Path, monkeypatch):
    path = tmp_path / "coding_backend_scores_full_test.json"
    path.write_text(
        json.dumps(
            [
                {"backend": "good", "score": 100, "ok": True},
                {"backend": "good", "score": 100, "ok": True},
                {"backend": "bad", "score": 0, "ok": False},
                {"backend": "bad", "score": 0, "ok": False},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mod,
        "latest_scores_path",
        lambda data_dir, full=False: path if full else None,
    )
    blocked = mod.demoted_backends(tmp_path, threshold=1.0)
    assert "bad" in blocked
    assert "good" not in blocked


def test_filter_coding_pool_preserves_order(tmp_path: Path, monkeypatch):
    path = tmp_path / "coding_backend_scores_full_test.json"
    path.write_text(
        json.dumps([{"backend": "b", "score": 0, "ok": False}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mod,
        "latest_scores_path",
        lambda data_dir, full=False: path if full else None,
    )
    out = mod.filter_coding_pool(["a", "b", "c"])
    assert out == ["a", "c"]


def test_pool_gate_disabled_returns_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LIMA_EVAL_POOL_GATE", "0")
    assert mod.demoted_backends(tmp_path) == frozenset()
