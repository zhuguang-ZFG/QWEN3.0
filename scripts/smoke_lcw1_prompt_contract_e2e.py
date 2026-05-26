#!/usr/bin/env python3
"""LC-W-1e smoke: create task with legacy goal → stored prompt_contract has 5 sections."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.prompt_contract import PromptContract, render_prompt_contract
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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"http_{exc.code}: {detail}") from exc


def main() -> int:
    if not _admin_token():
        print("SKIP: LIMA_ADMIN_TOKEN missing", file=sys.stderr)
        return 2

    created = _request(
        "POST",
        "/agent/tasks",
        {
            "repo": "D:/GIT",
            "goal": "LC-W-1e smoke: verify prompt contract sections",
            "constraints": ["read-only"],
            "test_commands": ["python -m pytest tests/test_prompt_contract.py -q"],
            "mode": "review",
            "allowed_tools": ["git_diff"],
        },
    )
    task_id = created.get("task_id", "")
    if not task_id:
        print("FAIL: missing task_id", file=sys.stderr)
        return 1

    envelope = _request("GET", f"/agent/tasks/{task_id}")
    contract = envelope.get("task", {}).get("prompt_contract") or {}
    if not contract.get("task"):
        print("FAIL: prompt_contract.task missing", file=sys.stderr)
        return 1

    rendered = render_prompt_contract(
        PromptContract(
            context=str(contract.get("context", "")),
            task=str(contract.get("task", "")),
            constraints=list(contract.get("constraints") or []),
            verify=list(contract.get("verify") or []),
            output=str(contract.get("output", "")),
        )
    )
    missing = [name for name in SECTIONS if name not in rendered]
    if missing:
        print(f"FAIL: render missing sections {missing}", file=sys.stderr)
        return 1

    print(json.dumps({"smoke_ok": True, "task_id": task_id, "sections": list(SECTIONS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
