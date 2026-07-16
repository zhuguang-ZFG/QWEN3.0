from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]"),
    re.compile(r"(?i)(api_key|apikey|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
]

# Production runtime packages and entrypoints that must exist and stay secret-clean.
RUNTIME_GLOBS = [
    "server_dlc.py",
    "access_guard.py",
    "runtime_env.py",
    "dlc_api/**/*.py",
    "dlc_core/**/*.py",
    "dlc_mcp/**/*.py",
    "device_gateway/**/*.py",
    "device_logic/**/*.py",
    "device_voice/**/*.py",
    "routes/**/*.py",
    "config/**/*.py",
    "common/**/*.py",
]


def _git_tracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def _runtime_targets() -> list[Path]:
    tracked = _git_tracked_files()
    selected: list[Path] = []
    for path in tracked:
        rel = path.relative_to(ROOT).as_posix()
        for pattern in RUNTIME_GLOBS:
            if path.match(pattern) or Path(rel).match(pattern):
                selected.append(path)
                break
    return selected


def test_runtime_files_do_not_contain_hardcoded_secret_literals():
    targets = _runtime_targets()
    assert targets, "runtime secret scan selected zero tracked files"
    offenders = []
    for path in targets:
        assert path.exists(), f"missing tracked runtime file: {path}"
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(path.relative_to(ROOT).as_posix())
                break
    assert offenders == []


def test_secret_scan_targets_exist():
    """CI-01: gate fails if the production tree is not present."""
    required = [
        ROOT / "server_dlc.py",
        ROOT / "dlc_api",
        ROOT / "device_gateway",
        ROOT / "routes",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert missing == []
