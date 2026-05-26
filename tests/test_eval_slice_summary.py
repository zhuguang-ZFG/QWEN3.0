"""Tests for eval JSON summary helpers."""

from __future__ import annotations

import json
from pathlib import Path

import eval_slice_summary as mod


def test_summarize_eval_json(tmp_path: Path):
    path = tmp_path / "coding_backend_scores_test.json"
    path.write_text(
        json.dumps(
            [
                {"backend": "a", "score": 90, "ok": True, "latency_ms": 1000},
                {"backend": "a", "score": 80, "ok": True, "latency_ms": 1200},
                {"backend": "b", "score": 50, "ok": False, "latency_ms": 2000},
            ]
        ),
        encoding="utf-8",
    )
    text = mod.summarize_eval_json(path)
    assert "a" in text
    assert "avg=85" in text
    assert "b" in text


def test_latest_scores_path_excludes_full(tmp_path: Path):
    quick = tmp_path / "coding_backend_scores_20260101.json"
    full = tmp_path / "coding_backend_scores_full_20260102.json"
    quick.write_text("[]", encoding="utf-8")
    full.write_text("[]", encoding="utf-8")
    full.touch()
    quick.touch()

    assert mod.latest_scores_path(tmp_path, full=False) == quick
    assert mod.latest_scores_path(tmp_path, full=True) == full
