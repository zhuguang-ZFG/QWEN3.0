"""Background MiMo jobs — spawn worker subprocess and track status on disk."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lima_mcp_stdio.mimo_runner import _artifact_dir
from lima_mcp_stdio.workspace import resolve_workspace

_JOB_STATUSES = ("queued", "running", "done", "failed")


def _jobs_root(workspace: Path) -> Path:
    root = _artifact_dir(workspace) / "jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_status(job_dir: Path, payload: dict[str, Any]) -> None:
    path = job_dir / "status.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _init_job(ws: Path, job_id: str, status: dict[str, Any]) -> tuple[Path, Path]:
    """Create job directory and persist initial status."""
    job_dir = _jobs_root(ws) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    _write_status(job_dir, status)
    return job_dir, job_dir / "worker.log"


def _build_worker_cmd(job_id: str, task: str, mode: str, ws: Path, scope: str | None, timeout: int | None) -> list[str]:
    """Build the worker subprocess command."""
    cmd = [
        sys.executable,
        "-m",
        "lima_mcp_stdio.job_worker",
        "--job-id",
        job_id,
        "--task",
        task,
        "--mode",
        mode,
        "--workspace",
        str(ws),
    ]
    if scope:
        cmd.extend(["--scope", scope])
    if timeout is not None:
        cmd.extend(["--timeout", str(timeout)])
    return cmd


def _spawn_worker(cmd: list[str], ws: Path, log_path: Path, status: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    """Spawn the worker process. Returns result dict."""
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
    try:
        with open(log_path, "w", encoding="utf-8") as log_fp:
            proc = subprocess.Popen(
                cmd,
                cwd=ws,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
                close_fds=False,
            )
    except OSError as exc:
        status["status"] = "failed"
        status["error"] = f"{type(exc).__name__}: {exc}"
        _write_status(job_dir, status)
        return {"ok": False, "job_id": status["job_id"], "error": status["error"]}
    status["status"] = "running"
    status["pid"] = proc.pid
    status["log_path"] = str(log_path)
    _write_status(job_dir, status)
    return {}


def start_async_run(
    *,
    task: str,
    mode: str = "review",
    scope: str | None = None,
    workspace: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Queue MiMo run in a detached worker; returns immediately."""
    task = (task or "").strip()
    if not task:
        return {"ok": False, "error": "task is required"}

    ws = resolve_workspace(workspace)
    job_id = uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    status = {
        "job_id": job_id,
        "status": "queued",
        "started_at": started_at,
        "task": task,
        "mode": mode,
        "scope": scope or "",
        "workspace": str(ws),
        "timeout": timeout,
    }
    job_dir, log_path = _init_job(ws, job_id, status)
    cmd = _build_worker_cmd(job_id, task, mode, ws, scope, timeout)
    err = _spawn_worker(cmd, ws, log_path, status, job_dir)
    if err:
        return err

    (_artifact_dir(ws) / "latest_job.json").write_text(
        json.dumps({"job_id": job_id, "started_at": started_at}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": "running",
        "workspace": str(ws),
        "job_dir": str(job_dir),
        "poll_tool": "lima_mimo_job_status",
        "hint": "Continue other work; poll job_status with this job_id before milestone closeout.",
    }


def job_status(*, job_id: str | None = None, workspace: str | None = None) -> dict[str, Any]:
    ws = resolve_workspace(workspace)
    root = _jobs_root(ws)

    if not job_id:
        latest = _artifact_dir(ws) / "latest_job.json"
        if latest.is_file():
            job_id = json.loads(latest.read_text(encoding="utf-8")).get("job_id")
        if not job_id:
            return {"ok": True, "status": "idle", "workspace": str(ws), "jobs": _list_jobs(root, limit=5)}

    job_dir = root / job_id
    status_path = job_dir / "status.json"
    if not status_path.is_file():
        return {"ok": False, "error": f"job not found: {job_id}"}

    data = json.loads(status_path.read_text(encoding="utf-8"))
    result_path = job_dir / "result.json"
    if result_path.is_file():
        data["result"] = json.loads(result_path.read_text(encoding="utf-8"))
    data["ok"] = data.get("status") == "done"
    return data


def _list_jobs(root: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not child.is_dir():
            continue
        sp = child / "status.json"
        if not sp.is_file():
            continue
        try:
            items.append(json.loads(sp.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
        if len(items) >= limit:
            break
    return items
