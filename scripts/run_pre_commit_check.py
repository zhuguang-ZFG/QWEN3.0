#!/usr/bin/env python3
"""Run deterministic LiMa pre-commit checks.

Default mode is intentionally quick for local commits. Use ``--full`` for the
documented CI-style pytest gate.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent

CI_PYTEST_IGNORES = [
    "tests/test_memory_daemon_ctl.py",
    "tests/test_healthcheck_ping.py",
    "tests/test_lima_smoke_task_script.py",
    "tests/test_gitee_mirror.py",
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


def quick_commands(staged_paths: Sequence[str], *, python: str = sys.executable) -> list[list[str]]:
    """Build quick pre-commit commands."""
    commands = [
        [python, "scripts/run_ruff_check.py"],
        ["git", "diff", "--cached", "--check"],
    ]
    compile_paths = [path for path in staged_paths if path.endswith(".py")]
    if compile_paths:
        commands.append([python, "-m", "py_compile", *compile_paths])
    return commands


def run_code_size_check(*, python: str = sys.executable) -> None:
    """Run code-size check as a non-blocking warning and print the report."""
    print("+ " + " ".join([python, "scripts/check_code_size.py"]), flush=True)
    result = subprocess.run([python, "scripts/check_code_size.py"], cwd=ROOT, check=False)
    if result.returncode != 0:
        print(
            "WARNING: code-size constraints violated (see above). "
            "This is a baseline check and does not block commits.",
            file=sys.stderr,
        )


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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        staged_paths = staged_python_files()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    commands = quick_commands(staged_paths)
    if args.full:
        basetemp = str(ROOT / "tmp" / f"pytest-run-precommit-full-{uuid.uuid4().hex}")
        commands.append(full_pytest_command(basetemp=basetemp))

    run_code_size_check()

    for command in commands:
        returncode = run_command(command)
        if returncode != 0:
            return returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
