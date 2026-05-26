#!/usr/bin/env python3
"""Upload local Netdata installer and run on VPS (PE-C-1 manual path)."""

from __future__ import annotations

import argparse
import os
import sys
import time

import paramiko

SERVER = "47.112.162.80"
REMOTE_PATH = "/tmp/netdata-x86_64-latest.gz.run"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 900) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "local_path",
        help="Path to netdata-x86_64-latest.gz.run on this machine",
    )
    args = parser.parse_args()

    local = os.path.abspath(args.local_path)
    if not os.path.isfile(local):
        sys.exit(f"file not found: {local}")

    size_mb = os.path.getsize(local) / (1024 * 1024)
    print(f"local_file={local} size_mb={size_mb:.1f}")
    if size_mb < 150:
        print(f"warn: expected ~181 MB, got {size_mb:.1f} MB — file may be incomplete")

    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    _run(ssh, "pkill -f netdata-kickstart 2>/dev/null || true", timeout=30)
    _run(ssh, "pkill -f netdata-x86_64-latest.gz.run 2>/dev/null || true", timeout=30)
    print("kickstart_stopped")

    print(f"uploading to {REMOTE_PATH} ...")
    sftp = ssh.open_sftp()
    sftp.put(local, REMOTE_PATH)
    sftp.close()
    print("upload_ok")

    install_cmd = (
        f"export DISABLE_TELEMETRY=1 && "
        f"{REMOTE_PATH} --accept -- --disable-telemetry"
    )
    print("install_start")
    code, out = _run(ssh, install_cmd, timeout=900)
    print(out[-3000:] if len(out) > 3000 else out)

    time.sleep(5)
    active = _run(ssh, "systemctl is-active netdata 2>/dev/null")[1].strip()
    info = _run(ssh, "curl -sf http://127.0.0.1:19999/api/v1/info 2>/dev/null | head -c 200")[1]
    ssh.close()

    ok = active == "active" and "version" in info.lower()
    print(f"service={active} api={info[:120]}")
    print("manual_install_ok" if ok else "manual_install_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
