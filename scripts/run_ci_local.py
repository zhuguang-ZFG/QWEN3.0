#!/usr/bin/env python3
"""Local mirror of .github/workflows/lima-ci.yml for pre-push verification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def main() -> int:
    steps = [
        [sys.executable, "-m", "pip", "install", "-r", "requirements_server.txt"],
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "pytest",
            "pytest-asyncio",
            "pytest-xdist",
            "pytest-cov",
            "pybreaker",
            "pip-audit",
            "ruff",
        ],
        [sys.executable, "scripts/run_ruff_check.py"],
        [sys.executable, "scripts/run_pip_audit.py"],
        [sys.executable, "scripts/run_rag_eval_gate.py"],
        [sys.executable, "-m", "pytest", "-q", "-m", "rag_gate"],
        [sys.executable, "scripts/run_pytest_ci.py"],
    ]
    for cmd in steps:
        code = run(cmd)
        if code != 0:
            return code
    print("Local CI mirror: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
