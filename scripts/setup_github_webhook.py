#!/usr/bin/env python3
"""Create or update GitHub repo webhook for LiMa (uses VPS .env GITHUB_TOKEN)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
REPO = "zhuguang-ZFG/QWEN3.0"
WEBHOOK_URL = "https://chat.donglicao.com/github/webhook"


def _run(ssh: paramiko.SSHClient, cmd: str) -> str:
    _i, o, e = ssh.exec_command(cmd)
    return (o.read() + e.read()).decode("utf-8", "replace").strip()


def _env_val(ssh: paramiko.SSHClient, key: str) -> str:
    line = _run(ssh, f"grep '^{key}=' {REMOTE}/.env | head -1")
    if not line or "=" not in line:
        return ""
    return line.split("=", 1)[1].strip()


def _github_api(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "LiMa-GH-Webhook-Setup/1.0",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {"status": resp.status}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} -> {exc.code}: {raw[:400]}") from exc


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    token = _env_val(ssh, "GITHUB_TOKEN")
    secret = _env_val(ssh, "GITHUB_WEBHOOK_SECRET")
    if not token:
        ssh.close()
        sys.exit("GITHUB_TOKEN missing on VPS .env")
    if not secret:
        ssh.close()
        sys.exit("GITHUB_WEBHOOK_SECRET missing on VPS .env")

    owner, name = REPO.split("/", 1)
    hooks = _github_api(token, "GET", f"/repos/{owner}/{name}/hooks?per_page=100")
    existing = None
    for hook in hooks if isinstance(hooks, list) else []:
        cfg = hook.get("config") or {}
        if cfg.get("url") == WEBHOOK_URL:
            existing = hook
            break

    payload = {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request", "workflow_run", "issues", "release"],
        "config": {
            "url": WEBHOOK_URL,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    }

    if existing:
        hook_id = existing["id"]
        result = _github_api(token, "PATCH", f"/repos/{owner}/{name}/hooks/{hook_id}", payload)
        print(f"updated webhook id={hook_id} url={WEBHOOK_URL}")
    else:
        result = _github_api(token, "POST", f"/repos/{owner}/{name}/hooks", payload)
        print(f"created webhook id={result.get('id')} url={WEBHOOK_URL}")

    ssh.close()
    print("github_webhook_setup_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
