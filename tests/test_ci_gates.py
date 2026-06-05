"""CI gate wrappers: ruff, pip-audit, pytest-ci entry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ruff_gate_passes():
    proc = subprocess.run(
        [sys.executable, "scripts/run_ruff_check.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p13_no_silent_exception_pass_in_active_paths():
    """Residual P1.3: no bare `except Exception: pass` in production-adjacent modules."""
    targets = [
        ROOT / "webhook_activity_buffer.py",
        ROOT / "gitee_webhook" / "dedupe.py",
        ROOT / "telegram_digest.py",
        ROOT / "streaming.py",
        ROOT / "http_sync.py",
        ROOT / "semantic_cache.py",
    ]
    bad: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        if "except Exception:\n        pass" in text or "except Exception:\n                pass" in text:
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"silent Exception pass remains: {bad}"


# Production trees scanned for forbidden legacy import (Slice 6).
_SMART_ROUTER_SCAN_ROOTS = (
    "routes",
    "agent_runtime",
    "context_pipeline",
    "session_memory",
    "channel_gateway",
    "device_gateway",
    "reverse_gateway",
    "search_gateway",
    "lima_mcp",
    "tool_gateway",
    "converters",
    "observability",
)
_SMART_ROUTER_ALLOWLIST_FILES = frozenset(
    {
        "smart_router.py",
    }
)


def _production_py_files() -> list[Path]:
    files: list[Path] = []
    for name in _SMART_ROUTER_SCAN_ROOTS:
        base = ROOT / name
        if base.is_dir():
            files.extend(base.rglob("*.py"))
    for path in ROOT.glob("*.py"):
        files.append(path)
    return files


def test_no_smart_router_imports_in_production():
    """Slice 6: forbid new ``import smart_router`` outside tests/scripts."""
    offenders: list[str] = []
    for path in _production_py_files():
        rel = path.relative_to(ROOT)
        if rel.parts and rel.parts[0] in ("tests", "scripts", "deploy"):
            continue
        if rel.name in _SMART_ROUTER_ALLOWLIST_FILES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("import smart_router") or stripped.startswith(
                "from smart_router"
            ):
                offenders.append(f"{rel}:{lineno}: {stripped}")
                break
    assert not offenders, "production must not import smart_router:\n" + "\n".join(offenders)
