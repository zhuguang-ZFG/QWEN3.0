"""CI gate wrappers: ruff, pip-audit, pytest-ci entry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_run_ruff_check_uses_tracked_python_files(monkeypatch, tmp_path):
    import scripts.run_ruff_check as run_ruff_check

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=b"server.py\0scripts/run_ruff_check.py\0notes.txt\0stub.pyi\0",
            stderr=b"",
        )

    monkeypatch.setattr(run_ruff_check.subprocess, "run", fake_run)

    assert run_ruff_check.tracked_python_files(tmp_path) == [
        "server.py",
        "scripts/run_ruff_check.py",
        "stub.pyi",
    ]
    assert calls[0][0] == ["git", "ls-files", "-z", "--", "*.py", "*.pyi"]
    assert calls[0][1]["cwd"] == tmp_path


def test_run_ruff_check_respects_config_excludes(monkeypatch, tmp_path):
    import scripts.run_ruff_check as run_ruff_check

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(run_ruff_check.subprocess, "run", fake_run)

    result = run_ruff_check.run_ruff(["server.py", "scripts/archive/old.py"], tmp_path)

    assert result.returncode == 0
    assert calls[0][0][:5] == [sys.executable, "-m", "ruff", "check", "--force-exclude"]
    assert calls[0][1]["cwd"] == tmp_path


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
