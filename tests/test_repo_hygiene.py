"""Repository hygiene: block high-risk tracked artifacts and local runtime leaks."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".pt",
    ".pth",
    ".bin",
    ".safetensors",
    ".gguf",
    ".zip",
    ".tar",
    ".tgz",
)

# Tracked exceptions only; prefer not to grow this list.
TRACKED_ALLOWLIST = set()

UNTRACKED_SCAN_DIRS = (
    ROOT / "data",
    ROOT / "scripts",
)

UNTRACKED_ALLOWLIST_PREFIXES = (
    "scripts/archive/",
)


def _git_ls_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        text=True,
        errors="replace",
    )
    return [p for p in out.split("\0") if p]


def _git_status_porcelain() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "status", "--porcelain", "-uall"],
        text=True,
        errors="replace",
    )
    return [line for line in out.splitlines() if line.strip()]


def _is_forbidden(path: str) -> bool:
    lower = path.replace("\\", "/").lower()
    return any(lower.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)


def test_tracked_files_exclude_high_risk_artifacts():
    violations = sorted(
        path
        for path in _git_ls_files()
        if _is_forbidden(path) and path not in TRACKED_ALLOWLIST
    )
    assert violations == [], f"tracked high-risk files: {violations}"


def test_worktree_has_no_untracked_high_risk_artifacts():
    offenders: list[str] = []
    for line in _git_status_porcelain():
        if not line.startswith("?? "):
            continue
        path = line[3:].strip().replace("\\", "/")
        if any(path.startswith(prefix) for prefix in UNTRACKED_ALLOWLIST_PREFIXES):
            continue
        if _is_forbidden(path):
            offenders.append(path)
    assert offenders == [], f"untracked high-risk files: {offenders}"


def test_external_repo_clones_gitignored():
    """Decoupled clones (opencode-source, deepcode-cli, esp32S_XYZ) must not be tracked."""
    text = (ROOT / ".gitignore").read_text(encoding="utf-8").replace("\\", "/")
    for name in ("opencode-source/", "deepcode-cli/", "esp32S_XYZ/"):
        assert name in text, f"missing gitignore entry: {name}"


def test_external_repos_doc_exists():
    doc = ROOT / "docs" / "EXTERNAL_REPOS.md"
    assert doc.is_file()
    body = doc.read_text(encoding="utf-8")
    assert "deepcode-cli" in body
    assert "opencode-source" in body


def test_scripts_archive_readme_exists():
    readme = ROOT / "scripts" / "archive" / "README.md"
    assert readme.is_file()
