#!/usr/bin/env python3
"""Dependency audit gate (pip-audit) for LiMa server requirements."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = ROOT / "requirements_server.txt"
IGNORE_FILE = ROOT / "data" / "pip_audit_ignore.json"


def _load_ignore_ids() -> set[str]:
    if not IGNORE_FILE.is_file():
        return set()
    try:
        payload = json.loads(IGNORE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"pip-audit: ignore file unreadable ({type(exc).__name__}): {exc}", file=sys.stderr)
        return set()
    ids = payload.get("ignore_vuln_ids", [])
    return {str(item) for item in ids}


def _run_pip_audit(requirements: Path, ignore_ids: set[str]) -> tuple[int, list[dict]]:
    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "-r",
        str(requirements),
        "--format",
        "json",
        "--progress-spinner",
        "off",
    ]
    for vuln_id in sorted(ignore_ids):
        cmd.extend(["--ignore-vuln", vuln_id])

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
        payload = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        print(proc.stdout, end="")
        print(proc.stderr, file=sys.stderr, end="")
        return 2, []

    findings: list[dict] = []
    for item in payload.get("dependencies", []):
        name = item.get("name", "?")
        version = item.get("version", "?")
        for vuln in item.get("vulns", []):
            findings.append(
                {
                    "name": name,
                    "version": version,
                    "id": vuln.get("id", "?"),
                    "fix_versions": vuln.get("fix_versions") or [],
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
    parser.add_argument(
        "--no-ignore-file",
        action="store_true",
        help="Do not load data/pip_audit_ignore.json",
    )
    args = parser.parse_args()

    if not args.requirements.is_file():
        print(f"pip-audit: requirements missing: {args.requirements}", file=sys.stderr)
        return 2

    ignore_ids = set() if args.no_ignore_file else _load_ignore_ids()
    code, findings = _run_pip_audit(args.requirements, ignore_ids)

    if code not in (0, 1):
        return code

    if not findings:
        print("pip-audit: no known vulnerabilities")
        return 0

    print(f"pip-audit: {len(findings)} finding(s)")
    for item in findings:
        fix = ", ".join(item["fix_versions"]) or "none listed"
        print(f"  - {item['name']} {item['version']} {item['id']} fix={fix}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
