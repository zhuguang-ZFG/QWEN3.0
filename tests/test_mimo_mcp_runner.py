"""Tests for lima_mcp_stdio (no live mimo CLI required)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import lima_mcp_stdio.mimo_runner as mr
from lima_mcp_stdio.mimo_invoke import InvokeResult


def test_status_without_findings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mr.mimo_invoke, "mimo_binary", lambda: None)
    out = mr.status(workspace=str(tmp_path))
    assert out["ok"] is False
    assert out["last_run"] is None
    assert "modes" in out


def test_review_requires_task():
    assert mr.review(task="")["ok"] is False


def test_review_merges_findings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_json = (
        '[{"id":"x","lane":"mimo","severity":"P1","title":"Leak","file":"a.py",'
        '"line":1,"evidence":"x","fix_hint":"y","test":"pytest"}]'
    )

    def fake_run_mimo(*_args, **_kwargs):
        out = _kwargs.get("output_path")
        if out:
            out.write_text(fake_json, encoding="utf-8")
        return InvokeResult(True, 0, fake_json, "", ["mimo", "run"])

    monkeypatch.setattr(mr.mimo_invoke, "mimo_binary", lambda: "/usr/bin/mimo")
    with patch.object(mr.mimo_invoke, "run_mimo", fake_run_mimo):
        out = mr.review(task="Review foo.py", scope="foo.py", workspace=str(tmp_path), timeout=30)

    assert out["ok"] is True
    assert out["findings_count"] == 1
    assert Path(out["paths"]["findings"]).is_file()


def test_verify_delta(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    artifact = tmp_path / ".omc" / "artifacts" / "mimo-mcp"
    artifact.mkdir(parents=True)
    baseline = {
        "task": "old",
        "findings": [
            {
                "id": "a",
                "lane": "mimo",
                "severity": "P1",
                "title": "Old",
                "file": "x.py",
                "line": 1,
                "evidence": "e1",
                "fix_hint": "",
                "test": "",
                "lanes": ["mimo"],
            }
        ],
    }
    (artifact / "findings.json").write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setenv("MIMO_MCP_ARTIFACT_DIR", str(artifact))

    def fake_run(**_kwargs):
        return {
            "ok": True,
            "findings": [],
            "paths": {"findings": str(artifact / "findings.json")},
        }

    with patch.object(mr, "run", fake_run):
        out = mr.verify(workspace=str(tmp_path))

    assert out["verify"]["closed"] == 1
    assert (artifact / "verify-delta.json").is_file()


def test_build_prompt_includes_mode():
    from lima_mcp_stdio.mimo_agents import build_prompt

    text = build_prompt("security", "scan auth", json_output=True)
    assert "security" in text
    assert "P0" in text
