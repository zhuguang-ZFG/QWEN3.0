"""Service restart and health-polling for unified VPS deploy."""

from __future__ import annotations

import json
import time

from scripts.deploy_common import SERVER, KEY, REMOTE, configure_ssh_host_keys
from scripts.deploy_unified_common import (
    HEALTH_GRACE_AFTER_RESTART_S,
    HEALTH_POLL_SECONDS,
    HEALTH_WAIT_SECONDS,
)
import paramiko


def _ssh_exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def restart_server() -> bool:
    """Clear pycache, restart the systemd service, and wait for health."""
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)

    try:
        commands = [
            f"find {REMOTE} -type d -name __pycache__ -exec rm -rf {{}} + 2>/dev/null",
            "systemctl restart lima-router",
        ]
        for cmd in commands:
            code, _out, err = _ssh_exec(ssh, cmd)
            if code != 0:
                print(f"restart command failed: {cmd}: {err}")
                return False

        if HEALTH_GRACE_AFTER_RESTART_S > 0:
            time.sleep(HEALTH_GRACE_AFTER_RESTART_S)

        deadline = time.time() + HEALTH_WAIT_SECONDS
        last_detail = ""
        while time.time() < deadline:
            # Fast-path: if the service already failed, stop polling immediately.
            active_code, _active_out, _active_err = _ssh_exec(
                ssh, "systemctl is-active lima-router"
            )
            if active_code != 0:
                print(f"  service not active (is-active exit {active_code}); fetching logs...")
                _code, logs, _err = _ssh_exec(
                    ssh, "journalctl -u lima-router -n 25 --no-pager"
                )
                if logs:
                    print(logs)
                return False

            code, out, err = _ssh_exec(ssh, "curl -sS -m 5 http://127.0.0.1:8080/health")
            last_detail = out or err or f"curl exit {code}"
            if code == 0:
                try:
                    payload = json.loads(out)
                    if payload.get("status") in ("ok", "warming"):
                        return True
                except json.JSONDecodeError:
                    pass
            time.sleep(HEALTH_POLL_SECONDS)

        print(f"  health never became ready; last: {last_detail[:240]}")
        _code, logs, _err = _ssh_exec(ssh, "journalctl -u lima-router -n 25 --no-pager")
        if logs:
            print(logs)
        return False
    finally:
        ssh.close()
