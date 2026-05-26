#!/usr/bin/env python3
"""Smoke SearXNG via LiMa dev_adapter on VPS (PE-D-1-2)."""

from __future__ import annotations

import json
import os
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 90) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    py = (
        f"cd {REMOTE} && set -a && . ./.env 2>/dev/null; set +a; "
        "/usr/local/bin/python3.10 -c \""
        "import json; from search_gateway.dev_adapter import get_dev_search_adapter; "
        "a=get_dev_search_adapter(); "
        "r=a.search('FastAPI Depends documentation', max_results=3); "
        "res=r.get('results') or []; "
        "print(json.dumps({'ok':r.get('ok'),'n':len(res),"
        "'source': (res[0].get('source','') if res else r.get('source','')),"
        "'fallback': r.get('fallback_from','')}, ensure_ascii=False))"
        "\""
    )
    code, out = _run(ssh, py, timeout=90)
    listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 8081 || true")[1]
    enabled = _run(ssh, f"grep '^SEARXNG_ENABLED=' {REMOTE}/.env 2>/dev/null || true")[1]
    ssh.close()

    print(f"searxng_env={enabled}")
    print(f"listen_8081={listen[:100]}")
    print(f"search={out[:300]}")
    try:
        data = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        data = {}
    ok = (
        data.get("ok")
        and "127.0.0.1:8081" in listen
        and (
            str(data.get("source", "")).startswith("searxng")
            or data.get("fallback") == "searxng"
        )
    )
    print("smoke_ok" if ok else "smoke_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
