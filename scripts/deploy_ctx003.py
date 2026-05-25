#!/usr/bin/env python3
"""Deploy CTX-003 Anthropic tool-route preflight to LiMa VPS."""

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
    "converters/anthropic_format.py",
    "routes/tool_forward.py",
    "lima_context.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
    try:
        out = stdout.read().decode("utf-8", errors="replace")
    except Exception:
        out = ""
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _run_smoke() -> None:
    import subprocess

    script = Path(__file__).resolve().parent / "vps_run_messages_smoke.py"
    _log("running /v1/messages smoke...")
    subprocess.run([sys.executable, str(script)], check=True)


def main() -> None:
    run_smoke = "--smoke" in sys.argv
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("no VPS backup (rollback via GitHub)")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        try:
            sftp.mkdir(remote_dir)
        except OSError:
            pass
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")
    sftp.close()

    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    time.sleep(3)
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(2)
    _run(
        ssh,
        (
            f"cd {REMOTE} && "
            "nohup /usr/local/bin/python3.10 server.py "
            "> /var/log/lima-server.log 2>&1 < /dev/null & echo $!"
        ),
        timeout=10,
    )
    time.sleep(6)

    port = _run(ssh, "ss -tlnp | grep 8080")
    if not port:
        _log("FAILED: " + _run(ssh, "tail -20 /var/log/lima-server.log"))
        ssh.close()
        sys.exit(1)

    _log("Server UP on 8080")
    ssh.close()

    if run_smoke:
        _run_smoke()


if __name__ == "__main__":
    main()
