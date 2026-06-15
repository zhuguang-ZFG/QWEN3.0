"""Detached worker entry — run one MiMo job and persist result.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lima_mcp_stdio import mimo_runner as mr
from lima_mcp_stdio.mimo_runner import _artifact_dir


def _job_dir(workspace: Path, job_id: str) -> Path:
    return _artifact_dir(workspace) / "jobs" / job_id


def _update_status(job_dir: Path, **fields) -> None:
    path = job_dir / "status.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MiMo MCP background job worker")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--mode", default="review")
    parser.add_argument("--scope", default="")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--timeout", type=int, default=None)
    args = parser.parse_args(argv)

    ws = Path(args.workspace).resolve()
    job_dir = _job_dir(ws, args.job_id)
    if not job_dir.is_dir():
        print(f"job dir missing: {job_dir}", file=sys.stderr)
        return 1

    _update_status(job_dir, status="running", worker_started_at=datetime.now(timezone.utc).isoformat())

    try:
        result = mr.run(
            task=args.task,
            mode=args.mode,
            scope=args.scope or None,
            workspace=str(ws),
            timeout=args.timeout,
        )
    except Exception as exc:
        _update_status(
            job_dir,
            status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            error=f"{type(exc).__name__}: {exc}",
        )
        return 1

    (job_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    final = "done" if result.get("ok") else "failed"
    _update_status(
        job_dir,
        status=final,
        finished_at=datetime.now(timezone.utc).isoformat(),
        findings_path=result.get("paths", {}).get("findings"),
        summary=result.get("summary"),
    )
    return 0 if final == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
