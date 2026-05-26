#!/usr/bin/env python3
"""Run security scan gates (Trivy + Grype + Syft, report-only)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_GATES: tuple[tuple[str, list[str]], ...] = (
    ("trivy", ["scripts/run_trivy.py", "--report-only"]),
    ("grype", ["scripts/run_grype.py", "--report-only"]),
    ("syft", ["scripts/run_syft.py", "--report-only"]),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any gate exits non-zero (default: report-only bundle)",
    )
    args = parser.parse_args()

    missing = 0
    failed = 0
    print("security_gates report-only bundle")
    for name, script_args in _GATES:
        cmd = [sys.executable, str(ROOT / script_args[0]), *script_args[1:]]
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        combined = ((proc.stdout or "") + (proc.stderr or "")).strip()
        tail = combined.splitlines()[-1] if combined else f"exit={proc.returncode}"
        if proc.returncode == 2:
            mark = "skip"
            missing += 1
        elif proc.returncode == 0:
            mark = "ok"
        else:
            mark = "FAIL"
            failed += 1
        print(f"  [{mark}] {name}: {tail}")

    if args.strict and (failed or missing):
        print(f"security_gates_fail failed={failed} missing={missing}")
        return 1
    print(f"security_gates_ok failed={failed} missing={missing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
