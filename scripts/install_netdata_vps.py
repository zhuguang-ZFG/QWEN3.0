#!/usr/bin/env python3
"""Install Netdata Agent on LiMa VPS (PE-C-1). Non-interactive kickstart."""

from __future__ import annotations

import os
import sys
import time

import paramiko

SERVER = "47.112.162.80"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 600) -> tuple[int, str]:
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

    code, pre = _run(ssh, "which netdata 2>/dev/null || echo missing", timeout=30)
    if "missing" not in pre.splitlines()[-1]:
        print(f"netdata_already_installed: {pre}")
        active = _run(ssh, "systemctl is-active netdata 2>/dev/null")[1].strip()
        if active == "active":
            ssh.close()
            print("install_netdata_vps_ok skipped=already_active")
            return 0

    kickstart = (
        "curl -fsSL https://get.netdata.cloud/kickstart.sh -o /tmp/netdata-kickstart.sh && "
        "sh /tmp/netdata-kickstart.sh --non-interactive --stable-channel "
        "--disable-telemetry --dont-wait"
    )
    print("install_netdata_vps_start")
    code, out = _run(ssh, kickstart, timeout=900)
    print(out[-2000:] if len(out) > 2000 else out)

    time.sleep(5)
    active = _run(ssh, "systemctl is-active netdata 2>/dev/null")[1].strip()
    info_code, info = _run(
        ssh,
        "curl -sf http://127.0.0.1:19999/api/v1/info 2>/dev/null | head -c 240",
        timeout=30,
    )
    key_paths = [
        "/var/lib/netdata/mcp_dev_preview_api_key",
        "/opt/netdata/var/lib/netdata/mcp_dev_preview_api_key",
    ]
    mcp_key_prefix = ""
    for path in key_paths:
        kc, key_out = _run(ssh, f"test -f {path} && head -c 8 {path} || true", timeout=15)
        if key_out.strip():
            mcp_key_prefix = key_out.strip()
            break

    ssh.close()
    ok = active == "active" and info_code == 0 and "version" in info.lower()
    print(f"service={active} api_info={'ok' if info_code == 0 else 'fail'} mcp_key_prefix={mcp_key_prefix or 'none'}")
    print("install_netdata_vps_ok" if ok else "install_netdata_vps_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
