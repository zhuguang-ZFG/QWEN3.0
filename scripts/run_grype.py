"""Run Grype vulnerability scan on server requirements (radar §四, report-only)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements_server.txt"


def _find_grype() -> str | None:
    found = shutil.which("grype")
    if found:
        return found
    for name in ("grype.exe", "grype"):
        candidate = ROOT / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _run_scan(grype: str, requirements: Path) -> tuple[int, str]:
    target = f"file:{requirements.resolve()}"
    cmd = [
        grype,
        target,
        "--fail-on",
        "high",
        "-o",
        "table",
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
        help="Exit 0 even when Grype reports vulnerabilities",
    )
    args = parser.parse_args()

    if not args.requirements.is_file():
        print(f"grype: requirements missing: {args.requirements}", file=sys.stderr)
        return 2

    grype = _find_grype()
    if not grype:
        print(
            "grype: binary not found (install from https://github.com/anchore/grype or CI step)",
            file=sys.stderr,
        )
        return 2

    code, output = _run_scan(grype, args.requirements)
    if code not in (0, 1):
        return code

    if output.strip():
        print(output.rstrip())
    if code == 0:
        print("grype: no HIGH+ findings")
        return 0

    if args.report_only:
        print("grype: findings reported (report-only)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
