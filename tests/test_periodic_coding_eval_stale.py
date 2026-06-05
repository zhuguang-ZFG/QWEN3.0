"""Stale-score detection for periodic coding eval."""

from __future__ import annotations

import time
from pathlib import Path

import periodic_coding_eval as pce


def test_scores_are_stale_when_file_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pce, "ROOT", tmp_path)
    stale, detail = pce.scores_are_stale()
    assert stale is True
    assert "no scores" in detail


def test_wait_server_ready_polls_until_ok(monkeypatch):
    calls = {"n": 0}

    def fake_check(_base: str = ""):
        calls["n"] += 1
        if calls["n"] < 2:
            return False, "refused"
        return True, "health ok"

    monkeypatch.setattr(pce, "check_eval_health", fake_check)
    ok, detail = pce._wait_server_ready(max_seconds=15)
    assert ok is True
    assert "health ok" in detail
    assert calls["n"] >= 2


def test_scores_are_stale_when_file_old(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = data_dir / "coding_backend_scores.json"
    path.write_text("[]", encoding="utf-8")
    old = time.time() - (10 * 86400)
    path.touch()
    import os

    os.utime(path, (old, old))
    monkeypatch.setattr(pce, "ROOT", tmp_path)
    monkeypatch.setattr(pce, "scores_max_age_seconds", lambda: 7 * 86400)
    stale, detail = pce.scores_are_stale()
    assert stale is True
    assert "age" in detail
