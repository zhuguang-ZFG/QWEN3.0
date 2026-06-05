"""Rebuild tier JSON from scores without live eval."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_coding_tiers_script(tmp_path: Path):
    scores = tmp_path / "scores.json"
    scores.write_text(
        json.dumps([
            {
                "backend": "demo_backend",
                "case_id": "python_bugfix",
                "score": 95,
                "latency_ms": 1000,
                "ok": True,
                "notes": [],
                "response_preview": "fixed",
            }
        ]),
        encoding="utf-8",
    )
    out = tmp_path / "tiers.json"
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "build_coding_tiers_from_scores.py"),
            "--scores",
            str(scores),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=root,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "demo_backend" in payload["backends"]
