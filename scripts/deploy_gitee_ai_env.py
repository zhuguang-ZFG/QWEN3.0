#!/usr/bin/env python3
"""Set GITEE_AI_TOKEN on VPS .env without printing the secret."""

from __future__ import annotations

import argparse
import os
import re
import sys

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router/.env"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
KEY_NAME = "GITEE_AI_TOKEN"


def _run(ssh: paramiko.SSHClient, cmd: str) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    code = stdout.channel.recv_exit_status()
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return code, out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", default=os.environ.get("GITEE_AI_TOKEN", ""))
    parser.add_argument("--enabled", choices=("0", "1"), default="0")
    args = parser.parse_args()
    token = (args.token or "").strip()
    if not token:
        sys.exit("GITEE_AI_TOKEN required (--token or env)")
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    code, content = _run(ssh, f"cat {REMOTE} 2>/dev/null || true")
    if code != 0 and content:
        ssh.close()
        sys.exit(content)

    lines = content.splitlines() if content else []
    new_lines: list[str] = []
    seen_token = False
    seen_enabled = False
    for line in lines:
        if line.startswith(f"{KEY_NAME}="):
            new_lines.append(f"{KEY_NAME}={token}")
            seen_token = True
            continue
        if line.startswith("GITEE_AI_ENABLED="):
            new_lines.append(f"GITEE_AI_ENABLED={args.enabled}")
            seen_enabled = True
            continue
        new_lines.append(line)
    if not seen_token:
        new_lines.append(f"{KEY_NAME}={token}")
    if not seen_enabled:
        new_lines.append(f"GITEE_AI_ENABLED={args.enabled}")

    payload = "\n".join(new_lines) + "\n"
    sftp = ssh.open_sftp()
    with sftp.open(REMOTE, "w") as fh:
        fh.write(payload)
    sftp.close()

    prefix = re.sub(r"(?<=.).(?=.)", "*", token[:8]) if len(token) >= 8 else "****"
    print(f"vps_env_ok {KEY_NAME}_prefix={prefix[:4]}...{prefix[-4:]} GITEE_AI_ENABLED={args.enabled}")
    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
