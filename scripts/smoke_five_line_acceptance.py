#!/usr/bin/env python3
"""Five-line closeout acceptance smokes (§4 checklist automation)."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
GITHUB_PUBLIC = os.environ.get(
    "GITHUB_WEBHOOK_PUBLIC_URL",
    "https://chat.donglicao.com/github/webhook",
)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _curl_github(payload: dict, secret: str, event: str) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        GITHUB_PUBLIC,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": _sign(body, secret),
            "User-Agent": "LiMa-Acceptance/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:300]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:300]


def check_mirror_lag() -> bool:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gitee_mirror_lag_check.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    print(proc.stdout.strip() or proc.stderr.strip())
    return proc.returncode == 0


def check_routing_config_vps(ssh: paramiko.SSHClient) -> bool:
    cmd = (
        f"cd {REMOTE} && /usr/local/bin/python3.10 -c "
        "\"import router_v3; "
        "cf=router_v3.POOLS['chat_fast']['strong'][0]; "
        "vis=router_v3.POOLS['vision']['medium'][:2]; "
        "print('chat_fast', cf); print('vision', vis)\""
    )
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if err:
        print(err, file=sys.stderr)
    print(out)
    ok = "google_flash_lite" in out and "cf_vision" in out and "google_flash" in out
    return ok


def check_github_issue_webhook(ssh: paramiko.SSHClient) -> bool:
    line = ""
    _stdin, stdout, _stderr = ssh.exec_command(
        f"grep '^GITHUB_WEBHOOK_SECRET=' {REMOTE}/.env | head -1",
        timeout=30,
    )
    raw = stdout.read().decode("utf-8", errors="replace").strip()
    if "=" in raw:
        secret = raw.split("=", 1)[1].strip()
    else:
        print("github_issue_webhook_FAILED missing secret")
        return False
    payload = {
        "action": "opened",
        "issue": {
            "number": 99999,
            "title": "acceptance smoke issue",
            "html_url": "https://github.com/zhuguang-ZFG/QWEN3.0/issues/99999",
        },
        "repository": {"full_name": "zhuguang-ZFG/QWEN3.0"},
    }
    code, body = _curl_github(payload, secret, event="issues")
    print(f"github_issue status={code} body={body[:120]}")
    return code == 200 and '"ok"' in body


def check_gitee_webhook() -> bool:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_gitee_webhook_public.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or proc.stderr).strip().splitlines()[-3:]
    print("\n".join(tail))
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-gitee", action="store_true")
    parser.add_argument("--skip-github-issue", action="store_true")
    args = parser.parse_args()

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    results: dict[str, bool] = {}
    results["mirror_lag"] = check_mirror_lag()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    results["routing_config"] = check_routing_config_vps(ssh)
    if not args.skip_github_issue:
        results["github_issue_webhook"] = check_github_issue_webhook(ssh)
    ssh.close()

    if not args.skip_gitee:
        results["gitee_webhook"] = check_gitee_webhook()

    failed = [k for k, ok in results.items() if not ok]
    print("acceptance_summary", results)
    if failed:
        print(f"acceptance_FAILED {','.join(failed)}")
        return 1
    print("acceptance_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
