"""Run Trivy vulnerability scan on server requirements (radar §四, report-only)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements_server.txt"


def _find_trivy() -> str | None:
    found = shutil.which("trivy")
    if found:
        return found
    for name in ("trivy.exe", "trivy"):
        candidate = ROOT / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _run_scan(trivy: str, requirements: Path) -> tuple[int, str]:
    cmd = [
        trivy,
        "fs",
        "--scanners",
        "vuln",
        "--severity",
        "HIGH,CRITICAL",
        "--format",
        "table",
        str(requirements),
    ]
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode not in (0, 1):
        print(output, end="")
        return proc.returncode, output
    return (0 if proc.returncode == 0 else 1), output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help=f"Requirements file (default: {DEFAULT_REQUIREMENTS.name})",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Exit 0 even when Trivy reports vulnerabilities",
    )
    args = parser.parse_args()

    if not args.requirements.is_file():
        print(f"trivy: requirements missing: {args.requirements}", file=sys.stderr)
        return 2

    trivy = _find_trivy()
    if not trivy:
        print(
            "trivy: binary not found (install from https://trivy.dev or CI step)",
            file=sys.stderr,
        )
        return 2

    code, output = _run_scan(trivy, args.requirements)
    if code not in (0, 1):
        return code

    if output.strip():
        print(output.rstrip())
    if code == 0:
        print("trivy: no HIGH/CRITICAL findings")
        return 0

    if args.report_only:
        print(f"trivy: findings reported (report-only)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
