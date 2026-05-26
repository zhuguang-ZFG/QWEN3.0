#!/usr/bin/env python3
"""OSV-Scanner gate for LiMa server requirements (complements pip-audit)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements_server.txt"


def _find_osv_scanner() -> str | None:
    found = shutil.which("osv-scanner")
    if found:
        return found
    for name in ("osv-scanner.exe", "osv-scanner"):
        candidate = ROOT / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


def _run_scan(scanner: str, requirements: Path) -> tuple[int, list[dict]]:
    cmd = [
        scanner,
        "scan",
        "--format",
        "json",
        f"--lockfile=requirements:{requirements}",
    ]
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    if proc.returncode not in (0, 1):
        print(proc.stdout, end="")
        print(proc.stderr, file=sys.stderr, end="")
        return proc.returncode, []

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        print(proc.stdout, end="")
        print(proc.stderr, file=sys.stderr, end="")
        return 2, []

    findings: list[dict] = []
    for result in payload.get("results", []):
        source = result.get("source", {})
        path = source.get("path", str(requirements))
        for pkg in result.get("packages", []):
            name = pkg.get("package", {}).get("name", "?")
            version = pkg.get("package", {}).get("version", "?")
            for vuln in pkg.get("vulnerabilities", []):
                findings.append(
                    {
                        "path": path,
                        "name": name,
                        "version": version,
                        "id": vuln.get("id", "?"),
                    }
                )
    return (0 if not findings else 1), findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help=f"Requirements file (default: {DEFAULT_REQUIREMENTS.name})",
    )
    args = parser.parse_args()

    if not args.requirements.is_file():
        print(f"osv-scanner: requirements missing: {args.requirements}", file=sys.stderr)
        return 2

    scanner = _find_osv_scanner()
    if not scanner:
        print(
            "osv-scanner: binary not found (install from "
            "https://google.github.io/osv-scanner/ or CI step)",
            file=sys.stderr,
        )
        return 2

    code, findings = _run_scan(scanner, args.requirements)
    if code not in (0, 1):
        return code

    if not findings:
        print("osv-scanner: no known vulnerabilities")
        return 0

    print(f"osv-scanner: {len(findings)} finding(s)")
    for item in findings:
        print(f"  - {item['name']} {item['version']} {item['id']} ({item['path']})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
