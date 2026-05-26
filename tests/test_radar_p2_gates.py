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


def test_filesystem_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_filesystem_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip filesystem_mcp" in proc.stdout


def test_github_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_github_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip github_mcp" in proc.stdout


def test_trivy_report_only_runs_or_skips():
    proc = subprocess.run(
        [sys.executable, "scripts/run_trivy.py", "--report-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    assert "trivy" in combined


def test_oldllm_diag_models_only_cli():
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/diag_oldllm_proxy.py",
            "--models-only",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert proc.returncode in (0, 1, 2), proc.stdout + proc.stderr
    assert "results" in proc.stdout


def test_postgres_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_postgres_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip postgres_mcp" in proc.stdout


def test_brave_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_brave_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip brave_mcp" in proc.stdout


def test_firecrawl_mcp_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_firecrawl_mcp.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip firecrawl_mcp" in proc.stdout


def test_syft_report_only_runs_or_skips():
    proc = subprocess.run(
        [sys.executable, "scripts/run_syft.py", "--report-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    assert "syft" in combined


def test_grype_report_only_runs_or_skips():
    proc = subprocess.run(
        [sys.executable, "scripts/run_grype.py", "--report-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    assert "grype" in combined


def test_eval_report_cli():
    proc = subprocess.run(
        [sys.executable, "scripts/run_eval_report.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "eval" in combined.lower() or "Eval" in combined


def test_mcp_gates_inventory():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_mcp_gates.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "mcp_gates_ok" in proc.stdout


def test_security_gates_bundle():
    proc = subprocess.run(
        [sys.executable, "scripts/run_security_gates.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "security_gates_ok" in proc.stdout


def test_ntfy_smoke_skips_when_disabled():
    proc = subprocess.run(
        [sys.executable, "scripts/smoke_ntfy.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "skip ntfy" in proc.stdout


def test_eval_full_report_skip_run():
    proc = subprocess.run(
        [sys.executable, "scripts/run_eval_full_and_report.py", "--skip-run", "--top", "3"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    combined = proc.stdout + proc.stderr
    assert "eval" in combined.lower() or "Eval" in combined


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
