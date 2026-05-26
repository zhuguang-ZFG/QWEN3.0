"""Smoke tests for radar P2 gate scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_playwright_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_playwright_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip playwright" in proc.stdout


def test_radar_eval_slice_dry_run():
    proc = subprocess.run(
        [sys.executable, "scripts/run_radar_eval_slice.py", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Cases:" in proc.stdout or "Backends" in proc.stdout


def test_radon_report_only_runs():
    proc = subprocess.run(
        [sys.executable, "scripts/run_radon.py", "--report-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "radon" in (proc.stdout + proc.stderr).lower()


def test_radar_eval_full_dry_run():
    proc = subprocess.run(
        [sys.executable, "scripts/run_radar_eval_slice.py", "--dry-run", "--full"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Backends (11):" in proc.stdout or "scnet_ds_flash" in proc.stdout


def test_fetch_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_fetch_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip fetch_mcp" in proc.stdout


def test_pyright_report_only_runs():
    proc = subprocess.run(
        [sys.executable, "scripts/run_pyright.py", "--report-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "pyright" in (proc.stdout + proc.stderr).lower()


def test_radar_eval_preflight_ok():
    proc = subprocess.run(
        [sys.executable, "scripts/run_radar_eval_slice.py", "--dry-run", "--preflight"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "eval_preflight_ok" in proc.stdout
