"""Tests for eval Telegram notify helper."""

from __future__ import annotations

from unittest.mock import patch

import eval_notify


def test_periodic_notify_defaults_on_when_periodic_enabled(monkeypatch):
    monkeypatch.setenv("LIMA_PERIODIC_CODING_EVAL", "1")
    monkeypatch.delenv("LIMA_PERIODIC_EVAL_NOTIFY_TG", raising=False)
    assert eval_notify.periodic_notify_enabled()


def test_build_message_includes_summary(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "coding_backend_scores_test.json").write_text(
        '[{"backend":"scnet_qwen30b","score":100,"ok":true,"latency_ms":100}]',
        encoding="utf-8",
    )
    # Patch ROOT to tmp_path
    monkeypatch.setattr(eval_notify, "ROOT", tmp_path)
    text = eval_notify._build_message(code=0, quick=True, source="periodic")
    assert "scnet_qwen30b" in text
    assert "exit=0" in text


def test_notify_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("LIMA_PERIODIC_CODING_EVAL", "0")
    monkeypatch.setenv("LIMA_PERIODIC_EVAL_NOTIFY_TG", "0")
    with patch.object(eval_notify.threading, "Thread") as mock_thread:
        eval_notify.notify_eval_finished(code=0, quick=True, source="periodic")
        mock_thread.assert_not_called()


def test_schedule_status_lines():
    lines = eval_notify.schedule_status_lines()
    assert any("LIMA_PERIODIC_CODING_EVAL" in line for line in lines)
