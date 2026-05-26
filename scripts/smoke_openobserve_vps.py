#!/usr/bin/env python3
"""Smoke OpenObserve ingest on VPS (PE-C-2)."""

from __future__ import annotations

import os
import sys

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 60) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    active = _run(ssh, "docker ps --filter name=lima-openobserve --format '{{.Status}}'")[1]
    listen = _run(ssh, "ss -tlnp 2>/dev/null | grep 5080 || true")[1]
    http = _run(ssh, "curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:5080/")[1]

    ingest = _run(
        ssh,
        "python3 -c \""
        "import base64,json,urllib.request;"
        "a=base64.b64encode(b'root@example.com:change-me-local').decode();"
        "d=json.dumps([{'event_type':'smoke_test','source':'smoke'}]).encode();"
        "r=urllib.request.Request('http://127.0.0.1:5080/api/default/lima_events/_json',"
        "data=d,headers={'Content-Type':'application/json','Authorization':'Basic '+a});"
        "print(urllib.request.urlopen(r,timeout=10).read().decode())"
        "\"",
    )

    ssh.close()
    print(f"container={active[:80]}")
    print(f"listen_5080={listen[:120]}")
    print(f"ui_http={http}")
    body = ingest[1]
    http_ok = '"code":200' in body or '"successful":1' in body
    print(f"ingest={body[:200]}")
    ok = "127.0.0.1:5080" in listen and http_ok
    print("smoke_ok" if ok else "smoke_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
