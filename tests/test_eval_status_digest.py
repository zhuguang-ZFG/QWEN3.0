"""Tests for eval_status and eval_digest."""

from __future__ import annotations

import json
import time

import eval_digest
import eval_status


def test_eval_file_lines_missing(tmp_path):
    lines = eval_status.eval_file_lines(tmp_path / "data")
    assert any("quick" in line and "（无）" in line for line in lines)
    assert any("full-11" in line for line in lines)


def test_eval_file_lines_with_files(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    quick = data / "coding_backend_scores_20260101.json"
    quick.write_text("[]", encoding="utf-8")
    full = data / "coding_backend_scores_full_20260101.json"
    full.write_text("[]", encoding="utf-8")
    lines = eval_status.eval_file_lines(data)
    assert any("quick" in line and quick.name in line for line in lines)
    assert any("full-11" in line and full.name in line for line in lines)


def test_large_eval_hint_when_zero(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    rows = [
        {"backend": "scnet_large_ds_flash", "score": 0, "ok": False},
        {"backend": "scnet_qwen30b", "score": 100, "ok": True},
    ]
    (data / "coding_backend_scores_full_x.json").write_text(
        json.dumps(rows), encoding="utf-8"
    )
    hint = eval_status.large_eval_hint_lines(data)
    assert hint
    assert "scnet_large_ds_flash" in "\n".join(hint)


def test_build_eval_status_includes_schedule(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("LIMA_PERIODIC_CODING_EVAL", "1")
    monkeypatch.setenv("LIMA_EVAL_POOL_GATE", "0")
    text = eval_status.build_eval_status(data, eval_busy=True)
    assert "Eval 运维总览" in text
    assert "manual_eval=运行中" in text
    assert "LIMA_PERIODIC_CODING_EVAL=1" in text


def test_build_eval_digest_merges_quick_and_full(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    row = [{"backend": "scnet_qwen30b", "score": 100, "ok": True, "latency_ms": 100}]
    (data / "coding_backend_scores_q.json").write_text(
        json.dumps(row), encoding="utf-8"
    )
    time.sleep(0.01)
    (data / "coding_backend_scores_full_f.json").write_text(
        json.dumps(row), encoding="utf-8"
    )
    text = eval_digest.build_eval_digest(data)
    assert "— quick —" in text
    assert "— full-11 —" in text
    assert "scnet_qwen30b" in text


def test_build_eval_digest_empty(tmp_path):
    text = eval_digest.build_eval_digest(tmp_path / "data")
    assert "尚无 eval JSON" in text
