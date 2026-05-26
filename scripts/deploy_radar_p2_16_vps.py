#!/usr/bin/env python3
"""Deploy radar P2-14..16 operator tools (/uuid, evalreport, oldllm) to VPS."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "eval_slice_summary.py",
    "oldllm_diag.py",
    "channel_gateway/public_apis_lookup.py",
    "channel_gateway/channel_tools.py",
    "channel_gateway/commands.py",
    "channel_gateway/tool_usage.py",
    "routes/telegram.py",
    "routes/telegram_public_tools.py",
    "routes/telegram_eval_tools.py",
    "routes/telegram_diag_tools.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 60) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = f"{REMOTE}/backups/radar-p2-16-{ts}"
    _run(ssh, f"mkdir -p {backup}/channel_gateway {backup}/routes")
    for rel in FILES:
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _run(ssh, f"test -f {remote} && cp {remote} {backup}/{rel} || true")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        remote_dir = os.path.dirname(remote)
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
        sftp.put(str(local), remote)
        print(f"uploaded {rel}")
    sftp.close()

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)

    active = _run(ssh, "systemctl is-active lima-router").strip()
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 160")
    print(f"service={active} health={health}")
    ok = active == "active" and health.strip()
    if ok:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deploy_common

        deploy_common.notify_deploy_success(
            ssh,
            "radar_p2_16",
            service=active,
            health=health[:160],
        )
    ssh.close()
    print("deploy_radar_p2_16_ok" if ok else "deploy_radar_p2_16_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
