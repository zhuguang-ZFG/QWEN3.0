#!/usr/bin/env python3
"""Minimal deploy for CQ-014 slice 11."""

import os
import sys
import time

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "routing_engine.py",
    "routing_classifier.py",
    "routing_selector.py",
    "routing_executor.py",
    "routes/admin.py",
    "routes/admin_state.py",
    "routes/admin_backends.py",
    "routes/admin_api.py",
]


def main() -> None:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY)
    sftp = ssh.open_sftp()

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = f"{REMOTE}/backups/cq014-slice11-{ts}"
    ssh.exec_command(f"mkdir -p {backup}")

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in FILES:
        local = os.path.join(base, rel)
        remote = f"{REMOTE}/{rel}"
        ssh.exec_command(f"cp {remote} {backup}/ 2>/dev/null || true")
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    ssh.exec_command("pkill -9 -f 'python3.10 server.py'")
    time.sleep(3)
    ssh.exec_command("fuser -k 8080/tcp 2>/dev/null")
    time.sleep(2)
    ssh.exec_command(
        f"cd {REMOTE} && nohup /usr/local/bin/python3.10 server.py > /var/log/lima-server.log 2>&1 &"
    )
    time.sleep(5)

    _stdin, stdout, _stderr = ssh.exec_command("ss -tlnp | grep 8080")
    port = stdout.read().decode().strip()
    if not port:
        _stdin, stdout, _stderr = ssh.exec_command("tail -10 /var/log/lima-server.log")
        print("FAILED:", stdout.read().decode())
        sys.exit(1)

    print("Server UP on 8080")
    print(f"Backup: {backup}")
    sftp.close()
    ssh.close()


if __name__ == "__main__":
    main()
