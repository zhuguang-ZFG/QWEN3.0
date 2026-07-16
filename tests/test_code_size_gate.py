"""Regression tests for the blocking product code-size gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts import check_code_size, run_pre_commit_check


def test_tool_and_virtualenv_trees_are_excluded() -> None:
    for path in (
        Path(".venv/Lib/site-packages/a.py"),
        Path(".venv-custom/pkg.py"),
        Path(".trellis/scripts/task.py"),
        Path(".agents/skills/tool.py"),
    ):
        assert check_code_size._should_skip(path)


def test_product_file_over_limit_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "routes" / "large.py"
    source.parent.mkdir()
    source.write_text("\n".join("value = 1" for _ in range(301)), encoding="utf-8")

    violations = check_code_size.check_files(tmp_path, lambda root: [source])

    assert violations == [(source, 301)]


def test_full_precommit_size_gate_checks_all_tracked_and_blocks(monkeypatch) -> None:
    calls: list[list[str]] = []

    def _run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(run_pre_commit_check.subprocess, "run", _run)

    rc = run_pre_commit_check.run_code_size_check([], python="py", full=True)

    assert rc == 1
    assert calls == [["py", "scripts/check_code_size.py", "--git-tracked"]]


def test_quick_precommit_size_gate_blocks_changed_violation(monkeypatch) -> None:
    monkeypatch.setattr(
        run_pre_commit_check.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 1),
    )

    assert run_pre_commit_check.run_code_size_check(["routes/large.py"], python="py") == 1
