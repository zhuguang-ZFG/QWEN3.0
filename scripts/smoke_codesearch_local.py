#!/usr/bin/env python3
"""Local smoke for PE-B-1 codesearch MCP (binary + rg baseline)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIXTURES = (
    ("routing_engine classify tier", "routing_engine.py"),
    ("telegram webhook secret verify", "routes/telegram.py"),
    ("health_tracker record_failure degraded", "health_recorder.py"),
)


def _pygrep(token: str, root: Path) -> tuple[bool, float, str]:
    start = time.perf_counter()
    token_l = token.lower()
    for path in root.rglob("*.py"):
        parts = path.parts
        if any(p in parts for p in ("venv", ".git", "node_modules", "__pycache__")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if token_l in text.lower():
            elapsed = time.perf_counter() - start
            rel = path.relative_to(root).as_posix()
            return True, elapsed, rel
    elapsed = time.perf_counter() - start
    return False, elapsed, ""


def _rg(query: str, root: Path) -> tuple[bool, float, str]:
    exe = shutil.which("rg") or shutil.which("rg.exe")
    token = query.split()[0]
    if not exe:
        return _pygrep(token, root)
    start = time.perf_counter()
    proc = subprocess.run(
        [exe, "-l", "-m", "1", query.split()[0], str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    elapsed = time.perf_counter() - start
    hit = proc.returncode == 0 and bool(proc.stdout.strip())
    sample = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else ""
    return hit, elapsed, sample


def _codesearch(query: str) -> tuple[bool, float, str]:
    exe = shutil.which("codesearch") or shutil.which("codesearch.exe")
    if not exe:
        return False, 0.0, "binary_missing"
    start = time.perf_counter()
    proc = subprocess.run(
        [exe, "search", query, "--limit", "3"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:120]
        return False, elapsed, detail or "search_failed"
    body = proc.stdout.strip()
    return bool(body), elapsed, body.splitlines()[0][:120] if body else "empty"


def main() -> int:
    enabled = os.environ.get("CODESEARCH_MCP_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    allow_raw = os.environ.get("CODESEARCH_INDEX_PATHS", f"{ROOT},{ROOT / 'deepcode-cli'}")
    allow_paths = [Path(p.strip()) for p in allow_raw.split(",") if p.strip()]

    print(f"enabled={enabled}")
    print(f"allowlist={[str(p) for p in allow_paths]}")
    print(f"root={ROOT}")

    rg_ok = 0
    for query, expect in FIXTURES:
        hit, elapsed, sample = _rg(query, ROOT)
        flag = "ok" if hit else "miss"
        if hit:
            rg_ok += 1
        print(f"rg_{flag} query={query!r} sec={elapsed:.3f} sample={sample or expect}")

    cs_binary = shutil.which("codesearch") or shutil.which("codesearch.exe")
    print(f"codesearch_binary={'yes' if cs_binary else 'no'}")

    cs_ok = 0
    if cs_binary:
        doctor = subprocess.run([cs_binary, "doctor"], capture_output=True, text=True, timeout=60)
        print(f"doctor_exit={doctor.returncode}")
        for query, _expect in FIXTURES:
            hit, elapsed, sample = _codesearch(query)
            flag = "ok" if hit else "miss"
            if hit:
                cs_ok += 1
            print(f"cs_{flag} query={query!r} sec={elapsed:.3f} sample={sample[:100]}")
    else:
        print("codesearch_skip=install per docs/CODESEARCH_MCP_SETUP.md")

    baseline_ok = rg_ok == len(FIXTURES)
    smoke_ok = baseline_ok and (cs_binary is None or cs_ok >= 1)
    print(f"rg_baseline={rg_ok}/{len(FIXTURES)}")
    if cs_binary:
        print(f"codesearch_hits={cs_ok}/{len(FIXTURES)}")
    print("smoke_ok" if smoke_ok else "smoke_FAILED")
    return 0 if smoke_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
