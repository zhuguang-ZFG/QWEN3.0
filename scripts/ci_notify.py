#!/usr/bin/env python3
"""Send CI status notification to Telegram via LiMa bot API.

Called from GitHub Actions workflow steps.
Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID secrets configured.

Usage:
  python scripts/ci_notify.py "CI passed" "LiMa CI on codex/free-web-ai-probe"
  python scripts/ci_notify.py "CI FAILED" "LiMa CI" --status failure
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("[ci_notify] Telegram not configured, skipping")
        return 0

    title = sys.argv[1] if len(sys.argv) > 1 else ""
    workflow = sys.argv[2] if len(sys.argv) > 2 else ""
    status = "failure" if "--status" in sys.argv else "success"

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    sha = (os.environ.get("GITHUB_SHA", ""))[:7]
    run_url = f"https://github.com/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"

    emoji = "✅" if status == "success" else "❌"
    lines = [
        f"{emoji} *{title}*",
        f"Workflow: `{workflow}`",
        f"Repo: `{repo}`@{branch}",
        f"Commit: `{sha}`",
        f"[View run]({run_url})",
    ]
    text = "\n".join(lines)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        if result.get("ok"):
            print("[ci_notify] sent")

            # Record to Outcome Ledger via LiMa internal API
            _try_record_outcome(repo, branch, sha, run_url, status, workflow)

            return 0
        print(f"[ci_notify] failed: {result}")
        return 1
    except Exception as exc:
        print(f"[ci_notify] error: {exc}")
        return 1


def _try_record_outcome(repo: str, branch: str, sha: str, run_url: str, status: str, workflow: str) -> None:
    """POST outcome event to LiMa internal endpoint (best-effort)."""
    lima_host = os.environ.get("LIMA_CI_OUTCOME_URL", "")
    lima_key = os.environ.get("LIMA_API_KEY", "lima-local")
    if not lima_host:
        return
    try:
        outcome_body = json.dumps({
            "source": "ci",
            "event_type": "workflow_run",
            "outcome": "success" if status == "success" else "failure",
            "task_id": sha,
            "scenario": "ci",
            "summary": f"{workflow} on {branch}: {status}",
            "tags": ["ci", status, branch],
        }).encode()
        req = urllib.request.Request(
            f"{lima_host}/internal/v1/outcome", data=outcome_body,
            headers={"Authorization": f"Bearer {lima_key}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        print("[ci_notify] outcome recorded")
    except Exception as exc:
        print(f"[ci_notify] outcome record failed: {exc}")

    # Auto-create LiMa task on CI failure
    if status != "success" and os.environ.get("LIMA_CI_AUTO_TASK", "0") == "1":
        _try_create_ci_fix_task(repo, branch, sha, run_url, lima_host, lima_key)


def _try_create_ci_fix_task(repo: str, branch: str, sha: str, run_url: str, host: str, key: str) -> None:
    """Create a LiMa task to investigate CI failure. Best-effort."""
    try:
        task_body = json.dumps({
            "repo": repo,
            "branch": branch,
            "goal": f"Fix CI failure on {branch} ({sha[:7]})",
            "instructions": [
                f"CI run failed: {run_url}",
                "1. Review the latest commit changes",
                "2. Run test suite locally to reproduce",
                "3. Fix the issue and verify tests pass",
                "4. Return needs_review with the fix",
            ],
            "allowed_tools": ["git_diff", "read_file", "test"],
            "mode": "patch",
            "max_runtime_sec": 600,
        }).encode()
        req = urllib.request.Request(
            f"{host}/agent/tasks", data=task_body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        print(f"[ci_notify] auto-task created: {result.get('task_id', '?')}")
    except Exception as exc:
        print(f"[ci_notify] auto-task failed: {exc}")
