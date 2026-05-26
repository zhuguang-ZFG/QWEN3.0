#!/usr/bin/env python3
"""Smoke Gitee webhook on VPS (signed POST) via public HTTPS."""

from __future__ import annotations

import argparse
import json
import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
PUBLIC_URL = os.environ.get(
    "GITEE_WEBHOOK_PUBLIC_URL",
    "https://chat.donglicao.com/gitee/webhook",
)

REMOTE_SMOKE = r"""
import json, os, urllib.request
from dotenv import load_dotenv
load_dotenv('/opt/lima-router/.env')
secret = os.environ.get('GITEE_WEBHOOK_SECRET', '')
payload = {
    'hook_name': 'push_hooks',
    'password': secret,
    'repository': {'path_with_namespace': 'zhuguang-cn/QWEN3.0'},
    'ref': 'refs/heads/codex/free-web-ai-probe',
    'commits': [{'id': 'smoke1234567890smoke1234567890smoke1234'}],
    'sender': {'username': 'lima-smoke'},
}
body = json.dumps(payload).encode()
req = urllib.request.Request(
    'http://127.0.0.1:8080/gitee/webhook',
    data=body,
    method='POST',
    headers={
        'Content-Type': 'application/json',
        'X-Gitee-Token': secret,
        'X-Gitee-Event': 'Push Hook',
    },
)
with urllib.request.urlopen(req, timeout=15) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8', errors='replace')[:200])
"""


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    return (stdout.read() + stderr.read()).decode("utf-8", "replace").strip()


def _curl_public(payload: dict, secret: str) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        PUBLIC_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Gitee-Token": secret,
            "X-Gitee-Event": "Push Hook",
            "User-Agent": "LiMa-Gitee-Smoke/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:300]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:300]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", help="Skip public HTTPS curl")
    args = parser.parse_args()

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    remote_path = f"{REMOTE}/scripts/_smoke_gitee_webhook_once.py"
    sftp = ssh.open_sftp()
    with sftp.file(remote_path, "w") as handle:
        handle.write(REMOTE_SMOKE)
    sftp.close()

    local_out = _run(ssh, f"/usr/local/bin/python3.10 {remote_path}")
    print(f"local_smoke:\n{local_out}")

    secret_line = _run(ssh, f"grep '^GITEE_WEBHOOK_SECRET=' {REMOTE}/.env | head -1")
    secret = secret_line.split("=", 1)[1].strip() if "=" in secret_line else ""

    ok = local_out.strip().startswith("200")
    if not args.local_only and secret:
        payload = {
            "hook_name": "push_hooks",
            "password": secret,
            "repository": {"path_with_namespace": "zhuguang-cn/QWEN3.0"},
            "ref": "refs/heads/main",
            "commits": [{"id": "publicsmoke1234567890publicsmoke1234567890"}],
            "sender": {"username": "lima-smoke"},
        }
        code, text = _curl_public(payload, secret)
        print(f"public_http={code} body={text[:200]}")
        ok = ok and code == 200

    ssh.close()
    if ok:
        print("smoke_gitee_webhook_ok")
        return 0
    print("smoke_gitee_webhook_FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
