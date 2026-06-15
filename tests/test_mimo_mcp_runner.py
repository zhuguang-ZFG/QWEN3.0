"""Tests for lima_mcp_stdio/mimo_runner (no live mimo CLI required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import lima_mcp_stdio.mimo_runner as mr


def _skill_merge_imports():
    skill = str(mr.SKILL_DIR)
    if skill not in sys.path:
        sys.path.insert(0, skill)
    from merge_findings import compare_findings_lists, merge_lane_artifacts, write_findings_bundle
    from scope import resolve_scope

    return merge_lane_artifacts, write_findings_bundle, compare_findings_lists, resolve_scope


def test_status_without_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "DEFAULT_ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mr.shutil, "which", lambda _: None)
    out = mr.status()
    assert out["ok"] is False
    assert out["last_run"] is None


def test_review_requires_task():
    assert mr.review(task="")["ok"] is False


def test_review_merges_mimo_lane(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "DEFAULT_ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(mr.shutil, "which", lambda _: "/usr/bin/mimo")

    fake_json = (
        '[{"id":"x","lane":"mimo","severity":"P1","title":"Leak","file":"a.py",'
        '"line":1,"evidence":"x","fix_hint":"y","test":"pytest"}]'
    )
    merge_lane_artifacts, write_findings_bundle, _, resolve_scope = _skill_merge_imports()

    class FakeResult:
        lane = "mimo"
        ok = True
        exit_code = 0
        error = ""
        output_path = tmp_path / "mimo.md"

    def fake_run_lane(*_args, **_kwargs):
        FakeResult.output_path.write_text(fake_json, encoding="utf-8")
        return FakeResult()

    def fake_write_brief(_root, out_dir, task, scope):
        path = out_dir / "review-brief.md"
        path.write_text(f"# {task}\nscope={scope}\n", encoding="utf-8")
        return path

    with patch.object(mr, "_skill_imports") as imp:
        imp.return_value = (
            fake_write_brief,
            fake_run_lane,
            merge_lane_artifacts,
            write_findings_bundle,
            _skill_merge_imports()[2],
            resolve_scope,
        )
        out = mr.review(task="Review routing_engine.py", scope="routing_engine.py", timeout=30)

    assert out["ok"] is True
    assert out["findings_count"] == 1
    assert out["summary"]["P1"] == 1
    findings_path = Path(out["paths"]["findings"])
    assert findings_path.is_file()
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    assert data["mode"] == "mimo-mcp"


def test_verify_delta(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "DEFAULT_ARTIFACT_DIR", tmp_path)
    baseline = {
        "task": "old task",
        "findings": [
            {
                "id": "a",
                "lane": "mimo",
                "severity": "P1",
                "title": "Old issue",
                "file": "x.py",
                "line": 1,
                "evidence": "e1",
                "fix_hint": "",
                "test": "",
                "lanes": ["mimo"],
            }
        ],
    }
    (tmp_path / "findings.json").write_text(json.dumps(baseline), encoding="utf-8")

    def fake_review(**_kwargs):
        return {
            "ok": True,
            "findings": [],
            "paths": {"findings": str(tmp_path / "findings.json")},
        }

    with patch.object(mr, "review", fake_review):
        out = mr.verify()

    assert out["verify"]["closed"] == 1
    assert out["verify"]["still_open"] == 0
    assert (tmp_path / "verify-delta.json").is_file()
