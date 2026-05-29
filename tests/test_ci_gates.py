"""CI gate wrappers: ruff, pip-audit, pytest-ci entry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ruff_gate_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/run_ruff_check.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p13_no_silent_exception_pass_in_active_paths():
    """Residual P1.3: no bare `except Exception: pass` in production-adjacent modules."""
    targets = [
        ROOT / "webhook_activity_buffer.py",
        ROOT / "gitee_webhook" / "dedupe.py",
        ROOT / "telegram_digest.py",
        ROOT / "streaming.py",
        ROOT / "http_sync.py",
        ROOT / "semantic_cache.py",
    ]
    bad: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if "except Exception:\n        pass" in text or "except Exception:\n                pass" in text:
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"silent Exception pass remains: {bad}"
