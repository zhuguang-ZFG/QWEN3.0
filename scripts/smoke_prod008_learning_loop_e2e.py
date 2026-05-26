#!/usr/bin/env python3
"""PROD-008 E2E: task create → result submit → learning loop four channels."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

BACKEND = "smoke_prod008"
SCENARIO = "agent_task"


def _base_url() -> str:
    return os.environ.get("LIMA_CODE_SERVER_URL", "http://127.0.0.1:8080").rstrip("/")


def _admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "").strip()


def _private_api_key() -> str:
    return os.environ.get("LIMA_API_KEY", "").strip()


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    token: str | None = None,
) -> dict:
    auth = token or _admin_token()
    if not auth:
        raise RuntimeError("LIMA_ADMIN_TOKEN not configured")
    url = f"{_base_url()}{path}"
    data = None
    headers = {"Authorization": f"Bearer {auth}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"http_{exc.code}: {detail}") from exc


def _ops_eval_candidates() -> int | None:
    key = _private_api_key()
    if not key:
        return None
    try:
        payload = _request("GET", "/v1/ops/metrics", token=key)
    except RuntimeError:
        return None
    loop = (payload.get("learning") or {}).get("loop") or {}
    val = loop.get("eval_candidates")
    return int(val) if isinstance(val, int) else None


def _entry_matches_task(entry: Any, task_id: str) -> bool:
    summary = getattr(entry, "summary", "") or ""
    detail = getattr(entry, "detail", "") or ""
    return task_id in summary or task_id in detail


def verify_learning_channels(
    task_id: str,
    *,
    backend: str = BACKEND,
    eval_before: int | None = None,
    eval_after: int | None = None,
) -> dict[str, Any]:
    """Verify persisted + in-process learning loop channels after HTTP ingest."""
    from session_memory.store import query_by_type

    routing_lessons = query_by_type("routing_lesson", limit=80)
    reference_patterns = query_by_type("reference_pattern", limit=80)

    channels: dict[str, bool | None] = {
        "memory": any(_entry_matches_task(e, task_id) for e in routing_lessons)
        or any(_entry_matches_task(e, task_id) for e in query_by_type("test_result", limit=80))
        or any(_entry_matches_task(e, task_id) for e in query_by_type("code_fact", limit=80)),
        "prompt": any(
            _entry_matches_task(e, task_id) and "prompt_profile:" in (e.summary or "")
            for e in reference_patterns
        ),
        "routing_memory": any(
            _entry_matches_task(e, task_id) and f"route:{backend}" in (e.summary or "")
            for e in routing_lessons
        ),
    }

    try:
        from context_pipeline.routing_weights import get_routing_weights

        stats = get_routing_weights().get_stats(backend, SCENARIO)
        channels["routing_weights"] = stats["successes"] >= 1
    except ImportError:
        channels["routing_weights"] = False

    channels["routing"] = bool(channels["routing_memory"]) or bool(channels["routing_weights"])

    if eval_before is not None and eval_after is not None:
        channels["eval"] = eval_after > eval_before
    else:
        channels["eval"] = None

    required = ("memory", "prompt", "routing")
    smoke_ok = all(channels[k] for k in required) and (
        channels["eval"] is None or channels["eval"] is True
    )
    return {"smoke_ok": smoke_ok, "task_id": task_id, "channels": channels}


def main() -> int:
    if not _admin_token():
        print("SKIP: LIMA_ADMIN_TOKEN missing", file=sys.stderr)
        return 2

    eval_before = _ops_eval_candidates()

    created = _request(
        "POST",
        "/agent/tasks",
        {
            "repo": "D:/GIT",
            "goal": "PROD-008 learning loop artifact → memory/routing smoke",
            "constraints": ["read-only smoke"],
            "test_commands": ["python -m pytest tests/test_learning_loop.py -q"],
            "mode": "review",
            "allowed_tools": ["git_diff"],
        },
    )
    task_id = created.get("task_id", "")
    if not task_id:
        print("FAIL: missing task_id", file=sys.stderr)
        return 1

    artifact_path = f".lima/artifacts/{task_id}/review/summary.md"
    result_body = {
        "task_id": task_id,
        "status": "needs_review",
        "summary": f"PROD-008 smoke task {task_id}",
        "changed_files": ["session_memory/learning_loop.py"],
        "test_commands": ["python -m pytest tests/test_learning_loop.py -q"],
        "test_results": [
            {
                "command": "python -m pytest tests/test_learning_loop.py -q",
                "exit_code": 0,
                "duration_ms": 120,
            }
        ],
        "diff_preview": "",
        "artifacts": [artifact_path],
        "risks": [],
        "next_action": "approve",
        "backend": BACKEND,
        "latency_ms": 1500,
    }
    submitted = _request("POST", f"/agent/tasks/{task_id}/result", result_body)
    if not submitted.get("accepted"):
        print("FAIL: result not accepted", file=sys.stderr)
        return 1

    events = _request("GET", f"/agent/tasks/{task_id}/events").get("events") or []
    if not any(e.get("type") == "result_submitted" for e in events):
        print("FAIL: missing result_submitted event", file=sys.stderr)
        return 1

    eval_after = _ops_eval_candidates()
    report = verify_learning_channels(
        task_id,
        backend=BACKEND,
        eval_before=eval_before,
        eval_after=eval_after,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("smoke_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
