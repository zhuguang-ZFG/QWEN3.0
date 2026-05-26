#!/usr/bin/env python3
"""Smoke GitHub webhook on VPS (signed POST) and optional real git push."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
PUBLIC_URL = os.environ.get(
    "GITHUB_WEBHOOK_PUBLIC_URL",
    "https://chat.donglicao.com/github/webhook",
)


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + "\n" + err).strip()


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _curl_public(payload: dict, secret: str, event: str = "push") -> tuple[int, str]:
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        PUBLIC_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": _sign(body, secret),
            "User-Agent": "LiMa-GH-Smoke/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:300]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:300]


def _get_secret(ssh: paramiko.SSHClient) -> str:
    line = _run(ssh, f"grep '^GITHUB_WEBHOOK_SECRET=' {REMOTE}/.env | head -1").strip()
    if not line or "=" not in line:
        line = _run(ssh, f"grep '^GITHUB_WEBHOOK_SECRET=' {REMOTE}/lima.env | head -1").strip()
    if not line or "=" not in line:
        sys.exit("GITHUB_WEBHOOK_SECRET not found on VPS lima.env")
    return line.split("=", 1)[1]


def smoke_signed_post(secret: str) -> bool:
    payload = {
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
        "ref": "refs/heads/codex/free-web-ai-probe",
        "pusher": {"name": "lima-smoke"},
        "commits": [{"id": "smoke0000000000000000000000000000000001"}],
    }
    code, body = _curl_public(payload, secret, event="push")
    print(f"public_signed_push status={code} body={body}")
    return code == 200 and '"ok"' in body


def smoke_journal(ssh: paramiko.SSHClient) -> bool:
    time.sleep(2)
    logs = _run(
        ssh,
        "journalctl -u lima-router --since '2 min ago' --no-pager 2>/dev/null | "
        "grep -iE 'github|telegram|webhook' | tail -8 || true",
    )
    print(f"journal_tail=\n{logs}")
    return bool(logs.strip())


def real_push(repo_root: Path, message: str) -> bool:
    marker = "docs/GITHUB_WEBHOOK_SMOKE.md"
    target = repo_root / marker
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    target.write_text(
        f"# GitHub Webhook Smoke\n\nAuto-generated: {stamp}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", marker], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
    subprocess.run(["git", "push", "origin", "HEAD"], cwd=repo_root, check=True)
    print(f"real_push_ok commit_message={message}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="Create empty smoke commit and push")
    parser.add_argument(
        "--message",
        default="chore: github webhook smoke marker",
    )
    args = parser.parse_args()

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)
    secret = _get_secret(ssh)

    ok_post = smoke_signed_post(secret)
    ok_log = smoke_journal(ssh)

    all_ok = ok_post and ok_log
    if all_ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_smoke_success(
            ssh,
            "github_webhook_public",
            detail=f"signed_post={ok_post} journal={ok_log}",
        )

    ok_push = True
    if args.push:
        ssh.close()
        ok_push = real_push(Path(__file__).resolve().parent.parent, args.message)
    else:
        ssh.close()

    print(
        f"summary signed_post={ok_post} journal={ok_log} push={ok_push if args.push else 'skipped'}",
    )
    return 0 if ok_post and ok_log and ok_push else 1


if __name__ == "__main__":
    raise SystemExit(main())
