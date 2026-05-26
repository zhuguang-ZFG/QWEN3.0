#!/usr/bin/env python3
"""LC-W-1e E2E: POST task → pending fetch → deepcode worker context.md has 5 sections."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SECTIONS = ("## Context", "## Task", "## Constraints", "## Verify", "## Output")


def _base_url() -> str:
    return os.environ.get("LIMA_CODE_SERVER_URL", "http://127.0.0.1:8080").rstrip("/")


def _admin_token() -> str:
    return os.environ.get("LIMA_ADMIN_TOKEN", "").strip()


def _request(method: str, path: str, body: dict | None = None) -> dict:
    token = _admin_token()
    if not token:
        raise RuntimeError("LIMA_ADMIN_TOKEN not configured")
    url = f"{_base_url()}{path}"
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
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


def _worker_verify(task: dict) -> dict:
    tsx = ROOT / "deepcode-cli" / "node_modules" / ".bin" / "tsx.cmd"
    if not tsx.is_file():
        tsx = ROOT / "deepcode-cli" / "node_modules" / ".bin" / "tsx"
    if not tsx.is_file():
        return {"skipped": True, "reason": "tsx_missing"}

    verify_ts = ROOT / "scripts" / "verify_lcw1_worker_context.ts"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(task, fh, ensure_ascii=False)
        task_path = fh.name
    try:
        proc = subprocess.run(
            [str(tsx), str(verify_ts), task_path, str(ROOT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    finally:
        Path(task_path).unlink(missing_ok=True)

    out = (proc.stdout or "").strip().splitlines()
    last = out[-1] if out else ""
    try:
        payload = json.loads(last)
    except json.JSONDecodeError:
        err = (proc.stderr or proc.stdout or "")[:300]
        raise RuntimeError(f"worker_verify_failed: {err}") from None
    if not payload.get("smoke_ok"):
        raise RuntimeError(f"worker_verify_failed: {payload}")
    return payload


def main() -> int:
    if not _admin_token():
        print("SKIP: LIMA_ADMIN_TOKEN missing", file=sys.stderr)
        return 2

    created = _request(
        "POST",
        "/agent/tasks",
        {
            "repo": "D:/GIT",
            "goal": "LC-W-1e /lima next: worker prompt contract smoke",
            "constraints": ["read-only smoke"],
            "test_commands": ["python -m pytest tests/test_prompt_contract.py -q"],
            "mode": "review",
            "allowed_tools": ["git_diff"],
        },
    )
    task_id = created.get("task_id", "")
    if not task_id:
        print("FAIL: missing task_id", file=sys.stderr)
        return 1

    pending = _request("GET", "/agent/tasks?status=accepted&limit=5")
    tasks = pending.get("tasks") or []
    if not any(str(t.get("task_id")) == task_id for t in tasks):
        print("FAIL: created task not in accepted pending list", file=sys.stderr)
        return 1

    envelope = _request("GET", f"/agent/tasks/{task_id}")
    task = envelope.get("task") or {}
    contract = task.get("prompt_contract") or {}
    if not contract.get("task"):
        print("FAIL: server prompt_contract.task missing", file=sys.stderr)
        return 1

    worker = _worker_verify(task)
    if worker.get("skipped"):
        print(
            json.dumps(
                {
                    "smoke_ok": True,
                    "task_id": task_id,
                    "server_only": True,
                    "worker": worker,
                    "sections": list(SECTIONS),
                },
                ensure_ascii=False,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "smoke_ok": True,
                "task_id": task_id,
                "server_only": False,
                "worker_context": worker.get("context_path"),
                "sections": list(SECTIONS),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
