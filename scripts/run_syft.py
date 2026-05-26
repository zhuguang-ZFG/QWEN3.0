"""Generate SBOM via Syft for server requirements (radar §四, report-only)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements_server.txt"


def _find_syft() -> str | None:
    found = shutil.which("syft")
    if found:
        return found
    for name in ("syft.exe", "syft"):
        candidate = ROOT / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _run_scan(syft: str, requirements: Path) -> tuple[int, str]:
    target = f"file:{requirements.resolve()}"
    cmd = [syft, "scan", target, "-o", "table"]
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
    return proc.returncode, output


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
        help="Exit 0 even when syft reports warnings",
    )
    args = parser.parse_args()

    if not args.requirements.is_file():
        print(f"syft: requirements missing: {args.requirements}", file=sys.stderr)
        return 2

    syft = _find_syft()
    if not syft:
        print(
            "syft: binary not found (install from https://github.com/anchore/syft or CI step)",
            file=sys.stderr,
        )
        return 2

    code, output = _run_scan(syft, args.requirements)
    if output.strip():
        print(output.rstrip())
    if code == 0:
        print("syft: sbom scan ok")
        return 0
    if args.report_only:
        print(f"syft: exit {code} (report-only)")
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
