"""MiMo lane orchestration — reuses lima-multi-cli skill modules (offline only)."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PROJECT_ROOT / ".claude" / "skills" / "lima-multi-cli"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / ".omc" / "artifacts" / "lima-multi-cli"
MIMO_LANE = "mimo"


def _skill_imports():
    import sys

    skill = str(SKILL_DIR)
    if skill not in sys.path:
        sys.path.insert(0, skill)
    from brief import write_brief
    from lanes import run_lane
    from merge_findings import compare_findings_lists, merge_lane_artifacts, write_findings_bundle
    from scope import resolve_scope

    return write_brief, run_lane, merge_lane_artifacts, write_findings_bundle, compare_findings_lists, resolve_scope


def _timeout(raw: int | None) -> int:
    if raw is not None:
        return max(30, min(raw, 600))
    try:
        return max(30, int(os.environ.get("LIMA_TIMEOUT", "180")))
    except ValueError:
        return 180


def _artifact_dir() -> Path:
    raw = os.environ.get("LIMA_MIMO_ARTIFACT_DIR", "").strip()
    return Path(raw).resolve() if raw else DEFAULT_ARTIFACT_DIR


def status() -> dict[str, Any]:
    """CLI availability + last findings summary."""
    binary = shutil.which("mimo")
    artifact_dir = _artifact_dir()
    payload: dict[str, Any] = {
        "ok": bool(binary),
        "mimo_cli": binary or "",
        "project_root": str(PROJECT_ROOT),
        "artifact_dir": str(artifact_dir),
        "skill_dir": str(SKILL_DIR),
    }
    findings_path = artifact_dir / "findings.json"
    if findings_path.is_file():
        data = json.loads(findings_path.read_text(encoding="utf-8"))
        payload["last_run"] = {
            "generated_at": data.get("generated_at"),
            "task": data.get("task"),
            "mode": data.get("mode"),
            "summary": data.get("summary"),
            "findings_path": str(findings_path),
        }
    else:
        payload["last_run"] = None
    return payload


def review(*, task: str, scope: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    """Run single MiMo lane and merge JSON findings."""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "task is required"}

    if not shutil.which("mimo"):
        return {"ok": False, "error": "mimo CLI not found on PATH"}

    write_brief, run_lane, merge_lane_artifacts, write_findings_bundle, _, resolve_scope = _skill_imports()

    artifact_dir = _artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    resolved_scope = resolve_scope(task, scope, PROJECT_ROOT)
    brief_path = write_brief(PROJECT_ROOT, artifact_dir, task, resolved_scope)
    lane_timeout = _timeout(timeout)

    result = run_lane(MIMO_LANE, task, brief_path, PROJECT_ROOT, artifact_dir, lane_timeout)
    lane_row = {
        "lane": result.lane,
        "ok": result.ok,
        "exit_code": result.exit_code,
        "error": result.error,
        "path": str(result.output_path),
    }

    findings = merge_lane_artifacts(artifact_dir, (MIMO_LANE,))
    findings_path, synthesis_path, fixpack_path = write_findings_bundle(
        artifact_dir, findings, [lane_row], task, "mimo-mcp"
    )

    log_path = artifact_dir / "execution.log"
    log_path.write_text(
        f"mimo-mcp {datetime.now(timezone.utc).isoformat()} ok={result.ok} exit={result.exit_code}\n",
        encoding="utf-8",
    )

    return {
        "ok": result.ok,
        "task": task,
        "scope": resolved_scope,
        "lane": lane_row,
        "findings_count": len(findings),
        "summary": _count_severity(findings),
        "findings": findings,
        "paths": {
            "brief": str(brief_path),
            "lane_output": str(result.output_path),
            "findings": str(findings_path),
            "synthesis": str(synthesis_path),
            "fix_pack": str(fixpack_path),
        },
    }


def verify(*, task: str | None = None, scope: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    """Re-run MiMo review and diff against previous findings.json."""
    artifact_dir = _artifact_dir()
    baseline_path = artifact_dir / "findings.json"
    if not baseline_path.is_file():
        return {"ok": False, "error": f"baseline not found: {baseline_path}"}

    old_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    old_findings = old_data.get("findings") or []
    run_task = (task or old_data.get("task") or "verify after fixes").strip()

    outcome = review(task=run_task, scope=scope, timeout=timeout)
    if not outcome.get("ok") and outcome.get("error"):
        return outcome

    new_findings = outcome.get("findings") or []
    _, _, _, _, compare_findings_lists, _ = _skill_imports()
    delta = compare_findings_lists(old_findings, new_findings)
    delta_path = artifact_dir / "verify-delta.json"
    delta_path.write_text(json.dumps(delta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    outcome["verify"] = {
        "delta_path": str(delta_path),
        "closed": len(delta["closed"]),
        "still_open": len(delta["still_open"]),
        "new": len(delta["new"]),
        "closed_items": delta["closed"],
        "still_open_items": delta["still_open"],
        "new_items": delta["new"],
    }
    return outcome


def _count_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for item in findings:
        sev = str(item.get("severity") or "P2").upper()
        if sev in counts:
            counts[sev] += 1
    return counts
