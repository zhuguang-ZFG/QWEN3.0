#!/usr/bin/env python3
"""Run deterministic LiMa pre-commit checks.

Default mode is intentionally quick for local commits. Use ``--full`` for the
documented CI-style pytest gate.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent

CI_PYTEST_IGNORES = [
    "tests/test_memory_daemon_ctl.py",
    "tests/test_healthcheck_ping.py",
    "tests/test_lima_smoke_task_script.py",
]


def staged_python_files(root: Path = ROOT) -> list[str]:
    """Return staged Python paths that are added/copied/modified/renamed."""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--diff-filter=ACMRT",
            "--",
            "*.py",
            "*.pyi",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git diff --cached failed: {stderr}")
    return [
        path
        for path in result.stdout.decode("utf-8", errors="replace").split("\0")
        if path and path.endswith((".py", ".pyi"))
    ]


def _git_has_parent(root: Path) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD~1"],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _git_changed_files_cmd(root: Path) -> subprocess.CompletedProcess:
    if _git_has_parent(root):
        return subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "-z",
                "--diff-filter=ACMRT",
                "HEAD~1",
                "HEAD",
                "--",
                "*.py",
                "*.pyi",
            ],
            cwd=root,
            capture_output=True,
            check=False,
        )
    # Shallow clone with a single commit: fall back to all tracked Python files.
    return subprocess.run(
        ["git", "ls-files", "-z", "*.py", "*.pyi"],
        cwd=root,
        capture_output=True,
        check=False,
    )


def changed_python_files_ci(root: Path = ROOT) -> list[str]:
    """Return changed Python paths for a CI run (HEAD~1..HEAD).

    Works for both ``push`` (HEAD~1 is the previous commit) and GitHub PR merge
    commits (HEAD~1 is the base branch).
    """
    result = _git_changed_files_cmd(root)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git diff HEAD~1..HEAD failed: {stderr}")
    return [
        path
        for path in result.stdout.decode("utf-8", errors="replace").split("\0")
        if path and path.endswith((".py", ".pyi"))
    ]


def quick_commands(changed_paths: Sequence[str], *, python: str = sys.executable, ci: bool = False) -> list[list[str]]:
    """Build quick pre-commit / CI commands."""
    commands = [
        [python, "scripts/run_ruff_check.py", *changed_paths],
    ]
    if ci:
        commands.append(["git", "diff", "--check", "HEAD~1", "HEAD"])
    else:
        commands.append(["git", "diff", "--cached", "--check"])
    compile_paths = [path for path in changed_paths if path.endswith(".py")]
    if compile_paths:
        commands.append([python, "-m", "py_compile", *compile_paths])
    return commands


def run_code_size_check(paths: Sequence[str], *, python: str = sys.executable) -> None:
    """Run code-size check as a non-blocking warning and print the report."""
    if not paths:
        print("No staged Python files; skipping code-size check.", flush=True)
        return
    command = [python, "scripts/check_code_size.py", *paths]
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        print(
            "WARNING: code-size constraints violated (see above). This is a baseline check and does not block commits.",
            file=sys.stderr,
        )


def run_testside_f401_safety_gate(paths: Sequence[str], *, python: str = sys.executable) -> int:
    """Run the test-side F401 safety gate (pytest --collect-only).

    Triggered when any staged file is under ``tests/``. Detects the (a)/(b)/(c)/(d)
    failure types documented in findings.md G1b lesson learned that ruff static
    analysis cannot see when `ruff --fix` removes test imports used by pytest
    string-matched fixture injection / module aliasing.

    Returns non-zero to BLOCK the commit when collection yields ERRORs.
    """
    test_paths = [p for p in paths if p.startswith("tests/") and p.endswith((".py", ".pyi"))]
    if not test_paths:
        # No test-side staged files → no safety gate needed.
        return 0
    # argparse action="append" expects one --paths per file, not --paths a b c.
    args_for_gate: list[str] = []
    for p in test_paths:
        args_for_gate.extend(["--paths", p])
    command = [python, "scripts/testside_f401_safety_gate.py", *args_for_gate]
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def full_pytest_command(*, python: str = sys.executable, basetemp: str | None = None) -> list[str]:
    """Build the documented CI-style pytest command."""
    command = [python, "-m", "pytest", "-p", "no:cacheprovider", "tests", "-q"]
    if basetemp:
        command.append(f"--basetemp={basetemp}")
    command.extend(f"--ignore={path}" for path in CI_PYTEST_IGNORES)
    return command


def run_command(command: Sequence[str], *, root: Path = ROOT) -> int:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=root, check=False).returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="also run the CI-style pytest command after quick checks",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="run in CI mode using HEAD~1..HEAD instead of staged changes",
    )
    return parser.parse_args(argv)


def _check_python_version() -> None:
    """Abort if not running under the supported Python 3.10 interpreter."""
    if sys.version_info[:2] != (3, 10):
        print(
            f"ERROR: run_pre_commit_check.py requires Python 3.10 (got {sys.version_info.major}.{sys.version_info.minor}). "
            "Activate .venv310 and retry.",
            file=sys.stderr,
        )
        sys.exit(1)


def main(argv: Sequence[str] | None = None) -> int:
    _check_python_version()
    args = parse_args(argv)
    try:
        changed_paths = changed_python_files_ci() if args.ci else staged_python_files()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    commands = quick_commands(changed_paths, ci=args.ci)
    if args.full:
        basetemp = str(Path(tempfile.gettempdir()) / f"pytest-run-precommit-full-{uuid.uuid4().hex}")
        commands.append(full_pytest_command(basetemp=basetemp))

    run_code_size_check(changed_paths)

    for command in commands:
        returncode = run_command(command)
        if returncode != 0:
            return returncode

    # The test-side F401 safety gate runs pytest --collect-only (takes ~3min),
    # so it's only invoked under --full to avoid slowing every local commit.
    if args.full:
        gate_rc = run_testside_f401_safety_gate(changed_paths)
        if gate_rc != 0:
            return gate_rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
