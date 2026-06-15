"""CLI gate for scripts/provider_automation/run_probe_batch.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "provider_automation" / "run_probe_batch.py"


def test_run_probe_batch_refuses_without_gate():
    env = {k: v for k, v in __import__("os").environ.items() if k != "LIMA_PROVIDER_AUTOMATION_RUN"}
    proc = subprocess.run(
        [sys.executable, str(CLI), "--limit", "1"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "LIMA_PROVIDER_AUTOMATION_RUN=1" in proc.stderr + proc.stdout
