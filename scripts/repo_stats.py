#!/usr/bin/env python3
"""Print LiMa repository Python statistics for CLAUDE.md refresh."""

from __future__ import annotations

from pathlib import Path

SKIP_PARTS = {
    "venv",
    ".git",
    "deepcode-cli",
    "donglicao",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "inkscape",
    "grblapp",
    "kxnx",
    "esp32S_XYZ",
    "esp32",
    "donglicao-site",
    "data",
}

KEY_FILES = (
    "server.py",
    "smart_router.py",
    "routing_engine.py",
    "http_body_limit.py",
    "semantic_cache.py",
    "routes/quality_gate.py",
    "routes/chat_handler_dispatch.py",
    "routes/system_endpoints.py",
    "backends.py",
    "routes/agent_tasks.py",
    "session_memory/store.py",
    "agent_runtime/orchestrator.py",
)


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    py_files = []
    for p in root.rglob("*.py"):
        if not p.is_file() or any(s in p.parts for s in SKIP_PARTS):
            continue
        py_files.append(p.relative_to(root))
    total_lines = sum(line_count(root / p) for p in py_files)
    tests = [p for p in py_files if p.parts[0] == "tests" and p.name.startswith("test_")]
    routes = [p for p in py_files if len(p.parts) >= 2 and p.parts[-2] == "routes"]
    top_dirs = {p.parts[0] for p in py_files if len(p.parts) > 1}

    print(f"python_files={len(py_files)}")
    print(f"python_lines={total_lines}")
    print(f"test_files_tests_dir={len(tests)}")
    print(f"routes_py_files={len(routes)}")
    print(f"routes_py_lines={sum(line_count(root / p) for p in routes)}")
    print(f"top_level_dirs={len(top_dirs)}")
    for name in KEY_FILES:
        path = root / name
        if path.exists():
            print(f"{name}={line_count(path)}")


if __name__ == "__main__":
    main()
