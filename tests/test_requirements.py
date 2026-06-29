"""Regression tests for dependency declarations (P3-17)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read_requirements() -> str:
    return (ROOT / "requirements_server.txt").read_text(encoding="utf-8")


def test_paramiko_minimum_version_has_no_known_cve():
    """paramiko must be pinned to >=3.5.0 to avoid CVE-2023-48795 etc.

    AUDIT-7-D4: accepts >=, ~=, or == constraints as long as the floor is >=3.5.0.
    """
    import re

    text = _read_requirements()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.lower().startswith("paramiko"):
            # Extract version from >=, ~=, or == constraint
            match = re.search(r"(?:>=|~=|==)(\d+\.\d+)", stripped)
            assert match, f"cannot parse paramiko version: {stripped}"
            major, minor = int(match.group(1).split(".")[0]), int(match.group(1).split(".")[1])
            assert (major, minor) >= (3, 5), f"paramiko version {match.group(1)} < 3.5.0: {stripped}"
            return
    raise AssertionError("paramiko not found in requirements_server.txt")
