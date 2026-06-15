"""CI gate wrappers: ruff, pip-audit, pytest-ci entry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_run_ruff_check_uses_tracked_python_files(monkeypatch, tmp_path):
    import scripts.run_ruff_check as run_ruff_check

    (tmp_path / "server.py").write_text("")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run_ruff_check.py").write_text("")
    (tmp_path / "notes.txt").write_text("")
    (tmp_path / "stub.pyi").write_text("")

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


def test_pre_commit_staged_python_files_filters_git_output(monkeypatch, tmp_path):
    import scripts.run_pre_commit_check as pre_commit_check

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=b"server.py\0README.md\0stub.pyi\0",
            stderr=b"",
        )

    monkeypatch.setattr(pre_commit_check.subprocess, "run", fake_run)

    assert pre_commit_check.staged_python_files(tmp_path) == ["server.py", "stub.pyi"]
    assert calls[0][0] == [
        "git",
        "diff",
        "--cached",
        "--name-only",
        "-z",
        "--diff-filter=ACMRT",
        "--",
        "*.py",
        "*.pyi",
    ]
    assert calls[0][1]["cwd"] == tmp_path


def test_pre_commit_quick_commands_use_tracked_gates():
    import scripts.run_pre_commit_check as pre_commit_check

    commands = pre_commit_check.quick_commands(["server.py", "types.pyi"], python="py")

    assert commands == [
        ["py", "scripts/run_ruff_check.py"],
        ["git", "diff", "--cached", "--check"],
        ["py", "-m", "py_compile", "server.py"],
    ]


def test_pre_commit_quick_commands_skip_compile_without_staged_python():
    import scripts.run_pre_commit_check as pre_commit_check

    commands = pre_commit_check.quick_commands([], python="py")

    assert commands == [
        ["py", "scripts/run_ruff_check.py"],
        ["git", "diff", "--cached", "--check"],
    ]


def test_pre_commit_full_command_uses_documented_ignores():
    import scripts.run_pre_commit_check as pre_commit_check

    command = pre_commit_check.full_pytest_command(python="py", basetemp="tmp/run")

    assert command[:6] == ["py", "-m", "pytest", "-p", "no:cacheprovider", "tests"]
    assert "--basetemp=tmp/run" in command
    for ignored in pre_commit_check.CI_PYTEST_IGNORES:
        assert f"--ignore={ignored}" in command


def test_ruff_gate_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/run_ruff_check.py"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # Handle encoding errors gracefully
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


_SILENT_EXCEPTION_PASS_SNIPPETS = (
    "except Exception:\n        pass",
    "except Exception:\n                pass",
    "except Exception:\n            pass",
)

_P13_SKIP_DIRS = frozenset(
    {
        "tests",
        "scripts",
        "esp32S_XYZ",
        "developer_skills",
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        ".venv310",
        "data",
        ".agents",
        ".codegraph",
    }
)


def _p13_scan_paths() -> list[Path]:
    paths: list[Path] = []
    for rel in ("device_gateway", "routes"):
        base = ROOT / rel
        if base.is_dir():
            paths.extend(sorted(base.rglob("*.py")))
    for pattern in ("routing_*.py", "http_*.py", "server*.py"):
        paths.extend(sorted(ROOT.glob(pattern)))
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if not path.is_file():
            continue
        if any(part in _P13_SKIP_DIRS or part.startswith(".venv") for part in path.parts):
            continue
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def test_p13_no_silent_exception_pass_in_active_paths():
    """P1.3 gate: no bare `except Exception: pass` in device/routing hot paths."""
    bad: list[str] = []
    for path in _p13_scan_paths():
        text = path.read_text(encoding="utf-8")
        if any(snippet in text for snippet in _SILENT_EXCEPTION_PASS_SNIPPETS):
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"silent Exception pass remains: {bad}"
