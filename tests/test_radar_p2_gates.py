"""Smoke tests for radar P2 gate scripts."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.subprocess_helpers import run_script

ROOT = Path(__file__).resolve().parent.parent
_PY = sys.executable


def test_playwright_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_playwright_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip playwright" in (proc.stdout or "")


def test_radar_eval_slice_dry_run():
    proc = run_script(
        [_PY, "scripts/run_radar_eval_slice.py", "--dry-run"],
        cwd=str(ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "Cases:" in (proc.stdout or "") or "Backends" in (proc.stdout or "")


def test_radon_report_only_runs():
    proc = run_script(
        [_PY, "scripts/run_radon.py", "--report-only"],
        cwd=str(ROOT),
        timeout=120,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "radon" in ((proc.stdout or "") + (proc.stderr or "")).lower()


def test_radar_eval_full_dry_run():
    proc = run_script(
        [_PY, "scripts/run_radar_eval_slice.py", "--dry-run", "--full"],
        cwd=str(ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    out = proc.stdout or ""
    assert "Backends (11):" in out or "scnet_ds_flash" in out


def test_fetch_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_fetch_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip fetch_mcp" in (proc.stdout or "")


def test_filesystem_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_filesystem_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip filesystem_mcp" in (proc.stdout or "")


def test_github_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_github_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip github_mcp" in (proc.stdout or "")


def test_trivy_report_only_runs_or_skips():
    proc = run_script(
        [_PY, "scripts/run_trivy.py", "--report-only"],
        cwd=str(ROOT),
        timeout=180,
    )
    combined = ((proc.stdout or "") + (proc.stderr or "")).lower()
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    assert "trivy" in combined


def test_oldllm_diag_models_only_cli():
    proc = run_script(
        [_PY, "scripts/diag_oldllm_proxy.py", "--models-only", "--json"],
        cwd=str(ROOT),
        timeout=60,
    )
    assert proc.returncode in (0, 1, 2), (proc.stdout or "") + (proc.stderr or "")
    assert "results" in (proc.stdout or "")


def test_postgres_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_postgres_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip postgres_mcp" in (proc.stdout or "")


def test_brave_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_brave_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip brave_mcp" in (proc.stdout or "")


def test_firecrawl_mcp_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_firecrawl_mcp.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip firecrawl_mcp" in (proc.stdout or "")


def test_syft_report_only_runs_or_skips():
    proc = run_script(
        [_PY, "scripts/run_syft.py", "--report-only"],
        cwd=str(ROOT),
        timeout=180,
    )
    combined = ((proc.stdout or "") + (proc.stderr or "")).lower()
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    assert "syft" in combined


def test_grype_report_only_runs_or_skips():
    proc = run_script(
        [_PY, "scripts/run_grype.py", "--report-only"],
        cwd=str(ROOT),
        timeout=180,
    )
    combined = ((proc.stdout or "") + (proc.stderr or "")).lower()
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    assert "grype" in combined


def test_eval_report_cli():
    proc = run_script([_PY, "scripts/run_eval_report.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "eval" in combined.lower() or "Eval" in combined


def test_mcp_gates_inventory():
    proc = run_script([_PY, "scripts/smoke_mcp_gates.py"], cwd=str(ROOT), timeout=300)
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "mcp_gates_ok" in (proc.stdout or "")


def test_security_gates_bundle():
    proc = run_script(
        [_PY, "scripts/run_security_gates.py"],
        cwd=str(ROOT),
        timeout=600,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "security_gates_ok" in (proc.stdout or "")


def test_ntfy_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_ntfy.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip ntfy" in (proc.stdout or "")


def test_eval_full_report_skip_run():
    proc = run_script(
        [_PY, "scripts/run_eval_full_and_report.py", "--skip-run", "--top", "3"],
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "eval" in combined.lower() or "Eval" in combined


def test_tg_archive_smoke_skips_when_disabled():
    proc = run_script([_PY, "scripts/smoke_tg_archive.py"], cwd=str(ROOT), timeout=30)
    assert proc.returncode == 0
    assert "skip tg_archive" in (proc.stdout or "")


def test_pyright_report_only_runs():
    proc = run_script(
        [_PY, "scripts/run_pyright.py", "--report-only"],
        cwd=str(ROOT),
        timeout=300,
    )
    assert proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    assert "pyright" in ((proc.stdout or "") + (proc.stderr or "")).lower()


def test_radar_eval_preflight_ok():
    proc = run_script(
        [_PY, "scripts/run_radar_eval_slice.py", "--dry-run", "--preflight"],
        cwd=str(ROOT),
        timeout=30,
    )
    assert proc.returncode in (0, 2), (proc.stdout or "") + (proc.stderr or "")
    ok = "eval_preflight_ok" in (proc.stdout or "")
    refused = "Connection refused" in (proc.stdout or "") or "Connection refused" in (proc.stderr or "")
    assert ok or refused, f"neither preflight_ok nor connection_refused: {proc.stdout}"
