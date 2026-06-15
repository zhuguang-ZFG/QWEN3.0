"""MiMo MCP orchestration — workspace-aware, Agent mode prompts, structured findings."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lima_mcp_stdio import mimo_agents, mimo_invoke
from lima_mcp_stdio.multi_cli import brief as brief_mod
from lima_mcp_stdio.multi_cli import merge_findings
from lima_mcp_stdio.multi_cli.scope import resolve_scope
from lima_mcp_stdio.workspace import resolve_workspace

MIMO_LANE = "mimo"
DEFAULT_ARTIFACT_SUBDIR = ".omc/artifacts/mimo-mcp"


def _timeout(raw: int | None) -> int:
    if raw is not None:
        return max(30, min(raw, 600))
    try:
        return max(30, int(os.environ.get("LIMA_TIMEOUT", os.environ.get("MIMO_MCP_TIMEOUT", "180"))))
    except ValueError:
        return 180


def _artifact_dir(workspace: Path) -> Path:
    raw = os.environ.get("MIMO_MCP_ARTIFACT_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (workspace / DEFAULT_ARTIFACT_SUBDIR).resolve()


def status(*, workspace: str | None = None) -> dict[str, Any]:
    ws = resolve_workspace(workspace)
    artifact_dir = _artifact_dir(ws)
    binary = mimo_invoke.mimo_binary()
    payload: dict[str, Any] = {
        "ok": bool(binary),
        "mimo_cli": binary or "",
        "workspace": str(ws),
        "artifact_dir": str(artifact_dir),
        "modes": mimo_agents.list_modes(),
        "env": {
            "MIMO_MCP_WORKSPACE": os.environ.get("MIMO_MCP_WORKSPACE", ""),
            "MIMO_MCP_AGENT": os.environ.get("MIMO_MCP_AGENT", ""),
            "MIMO_MCP_MODEL": os.environ.get("MIMO_MCP_MODEL", ""),
        },
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
    done_path = artifact_dir / "last_done.json"
    if done_path.is_file():
        payload["last_done"] = json.loads(done_path.read_text(encoding="utf-8"))
    return payload


def poll(*, workspace: str | None = None) -> dict[str, Any]:
    """Read completion marker without re-running MiMo."""
    ws = resolve_workspace(workspace)
    artifact_dir = _artifact_dir(ws)
    out: dict[str, Any] = {
        "workspace": str(ws),
        "artifact_dir": str(artifact_dir),
        "findings_path": str(artifact_dir / "findings.json"),
        "last_done_path": str(artifact_dir / "last_done.json"),
    }
    done_path = artifact_dir / "last_done.json"
    if done_path.is_file():
        out["last_done"] = json.loads(done_path.read_text(encoding="utf-8"))
        out["ready"] = True
    else:
        out["ready"] = False
    findings_path = artifact_dir / "findings.json"
    if findings_path.is_file():
        data = json.loads(findings_path.read_text(encoding="utf-8"))
        out["summary"] = data.get("summary")
        out["findings_count"] = len(data.get("findings") or [])
    return out


def run(
    *,
    task: str,
    mode: str = "review",
    scope: str | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
    json_findings: bool = True,
    session_continue: bool = False,
) -> dict[str, Any]:
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "task is required"}
    if not mimo_invoke.mimo_binary():
        return {"ok": False, "error": "mimo CLI not found on PATH"}

    ws = resolve_workspace(workspace)
    artifact_dir = _artifact_dir(ws)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    resolved_scope = resolve_scope(task, scope, ws)
    brief_path = brief_mod.write_brief(ws, artifact_dir, task, resolved_scope)

    attach: list[Path] = [brief_path]
    if resolved_scope:
        scope_path = ws / resolved_scope
        if scope_path.is_file():
            attach.append(scope_path)

    prior_findings = artifact_dir / "findings.json"
    if mode == "verify" and prior_findings.is_file():
        attach.append(prior_findings)

    prompt = mimo_agents.build_prompt(mode, task, json_output=json_findings)
    agent = mimo_agents.resolve_agent(mode)
    lane_timeout = _timeout(timeout)
    out_path = artifact_dir / f"{MIMO_LANE}.md"

    invoke = mimo_invoke.run_mimo(
        prompt,
        ws,
        attach_files=attach,
        agent=agent,
        session_continue=session_continue,
        timeout=lane_timeout,
        output_path=out_path,
    )

    lane_row = {
        "lane": MIMO_LANE,
        "ok": invoke.ok,
        "exit_code": invoke.exit_code,
        "error": "" if invoke.ok else "invoke failed",
        "path": str(out_path),
        "mode": mode,
        "command": invoke.command,
    }

    findings = merge_findings.merge_lane_artifacts(artifact_dir, (MIMO_LANE,))
    mode_tag = f"mimo-mcp-{mode}"
    findings_path, synthesis_path, fixpack_path = merge_findings.write_findings_bundle(
        artifact_dir, findings, [lane_row], task, mode_tag
    )

    (artifact_dir / "execution.log").write_text(
        f"{mode_tag} {datetime.now(timezone.utc).isoformat()} ok={invoke.ok} exit={invoke.exit_code}\n",
        encoding="utf-8",
    )

    done_flag = artifact_dir / "last_done.json"
    done_flag.write_text(
        json.dumps(
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "ok": invoke.ok,
                "mode": mode,
                "task": task,
                "findings_path": str(findings_path),
                "summary": _count_severity(findings),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "ok": invoke.ok,
        "task": task,
        "mode": mode,
        "scope": resolved_scope,
        "workspace": str(ws),
        "lane": lane_row,
        "findings_count": len(findings),
        "summary": _count_severity(findings),
        "findings": findings,
        "paths": {
            "brief": str(brief_path),
            "lane_output": str(out_path),
            "findings": str(findings_path),
            "synthesis": str(synthesis_path),
            "fix_pack": str(fixpack_path),
        },
    }


def review(*, task: str, scope: str | None = None, workspace: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    return run(task=task, mode="review", scope=scope, workspace=workspace, timeout=timeout)


def verify(*, task: str | None = None, scope: str | None = None, workspace: str | None = None, timeout: int | None = None) -> dict[str, Any]:
    ws = resolve_workspace(workspace)
    artifact_dir = _artifact_dir(ws)
    baseline_path = artifact_dir / "findings.json"
    if not baseline_path.is_file():
        return {"ok": False, "error": f"baseline not found: {baseline_path}"}

    old_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    old_findings = old_data.get("findings") or []
    run_task = (task or old_data.get("task") or "verify after fixes").strip()

    outcome = run(task=run_task, mode="verify", scope=scope, workspace=str(ws), timeout=timeout)
    if outcome.get("error") and not outcome.get("findings"):
        return outcome

    new_findings = outcome.get("findings") or []
    delta = merge_findings.compare_findings_lists(old_findings, new_findings)
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
