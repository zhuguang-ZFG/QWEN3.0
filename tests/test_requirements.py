"""Regression tests for dependency declarations (P3-17)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read_requirements() -> str:
    return (ROOT / "requirements_server.txt").read_text(encoding="utf-8")


def test_paramiko_minimum_version_has_no_known_cve():
    """paramiko must be pinned/lower-bounded to >=3.5.0 to avoid CVE-2023-48795 etc."""
    text = _read_requirements()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.lower().startswith("paramiko"):
            assert ">=3.5.0" in stripped, f"paramiko declaration missing >=3.5.0: {stripped}"
            return
    raise AssertionError("paramiko not found in requirements_server.txt")
