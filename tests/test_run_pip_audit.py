"""Tests for scripts/run_pip_audit.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pip_audit_gate_clean_on_server_requirements():
    proc = subprocess.run(
        [sys.executable, "scripts/run_pip_audit.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no known vulnerabilities" in proc.stdout


def test_load_ignore_ids(tmp_path: Path, monkeypatch):
    ignore_path = tmp_path / "pip_audit_ignore.json"
    ignore_path.write_text(
        json.dumps({"ignore_vuln_ids": ["PYSEC-TEST-1"]}),
        encoding="utf-8",
    )
    import scripts.run_pip_audit as mod

    monkeypatch.setattr(mod, "IGNORE_FILE", ignore_path)
    assert mod._load_ignore_ids() == {"PYSEC-TEST-1"}
