"""Tests for eval preflight and periodic coding eval wiring."""

from __future__ import annotations

import periodic_coding_eval
from eval_preflight import check_eval_health, full_backend_list, quick_backend_list


def test_quick_backend_defaults():
    names = quick_backend_list()
    assert len(names) >= 2
    assert "scnet_qwen30b" in names or "kimi" in names


def test_check_eval_health_local(monkeypatch):
    class FakeResp:
        status = 200

        def read(self, n=-1):
            return b'{"status":"ok"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "eval_preflight.urllib.request.urlopen",
        lambda *a, **k: FakeResp(),
    )
    ok, detail = check_eval_health("http://127.0.0.1:8080")
    assert ok
    assert "ok" in detail


def test_full_backend_defaults():
    names = full_backend_list()
    assert len(names) == 11
    assert "scnet_ds_flash" in names
    assert "kimi" in names


def test_periodic_eval_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LIMA_PERIODIC_CODING_EVAL", raising=False)
    assert not periodic_coding_eval.enabled()


def test_periodic_eval_run_slice_invokes_script(monkeypatch):
    calls: list[list[str]] = []

    def fake_call(cmd, cwd=None):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(periodic_coding_eval.subprocess, "call", fake_call)
    code = periodic_coding_eval.run_eval_slice(quick=True)
    assert code == 0
    assert calls
    assert "run_radar_eval_slice.py" in calls[0][1]
    assert "--preflight" in calls[0]
    assert "--quick" in calls[0]
