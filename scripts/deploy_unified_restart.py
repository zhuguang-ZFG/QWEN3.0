"""Service restart and health-polling for unified VPS deploy."""

from __future__ import annotations

import json
import time

from scripts.deploy_common import configure_ssh_host_keys
from scripts.deploy_unified_common import (
    HEALTH_GRACE_AFTER_RESTART_S,
    HEALTH_POLL_SECONDS,
    HEALTH_WAIT_SECONDS,
    DeployTarget,
    READY_POLL_SECONDS,
    READY_WAIT_SECONDS,
)
import paramiko


def _ssh_exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def _connect_ssh(target: DeployTarget) -> paramiko.SSHClient:
    """Open an SSH connection to the deploy target using key or password fallback."""
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    try:
        ssh.connect(target.host, username=target.user, key_filename=target.key_path, timeout=15)
    except paramiko.SSHException:
        if not target.password:
            raise
        ssh.connect(target.host, username=target.user, password=target.password, timeout=15)
    return ssh


def _restart_service(ssh: paramiko.SSHClient) -> bool:
    code, _out, err = _ssh_exec(ssh, "systemctl restart lima-router")
    if code != 0:
        print(f"restart command failed: {err}")
        return False
    if HEALTH_GRACE_AFTER_RESTART_S > 0:
        time.sleep(HEALTH_GRACE_AFTER_RESTART_S)
    return True


def _service_is_active(ssh: paramiko.SSHClient) -> bool:
    active_code, _active_out, _active_err = _ssh_exec(ssh, "systemctl is-active lima-router")
    if active_code != 0:
        print(f"  service not active (is-active exit {active_code}); fetching logs...")
        _code, logs, _err = _ssh_exec(ssh, "journalctl -u lima-router -n 25 --no-pager")
        if logs:
            print(logs)
        return False
    return True


def _health_ready(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    """Use /health/ready instead of /health to avoid the slow circuit-breaker scan."""
    code, out, err = _ssh_exec(ssh, "curl -sS -m 30 http://127.0.0.1:8080/health/ready")
    last_detail = out or err or f"curl exit {code}"
    if code == 0:
        try:
            payload = json.loads(out)
            if payload.get("startup_status") in ("ready", "warming"):
                return True, last_detail
        except json.JSONDecodeError:
            pass
    return False, last_detail


def _ready_ready(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    code, out, err = _ssh_exec(ssh, "curl -sS -m 30 http://127.0.0.1:8080/health/ready")
    last_detail = out or err or f"curl exit {code}"
    if code == 0:
        try:
            payload = json.loads(out)
            if payload.get("status") == "ready":
                return True, last_detail
        except json.JSONDecodeError:
            pass
    return False, last_detail


def _poll_health(ssh: paramiko.SSHClient) -> bool:
    deadline = time.time() + HEALTH_WAIT_SECONDS
    last_detail = ""
    while time.time() < deadline:
        if not _service_is_active(ssh):
            return False
        ready, last_detail = _health_ready(ssh)
        if ready:
            return True
        time.sleep(HEALTH_POLL_SECONDS)

    print(f"  health never became ready; last: {last_detail[:240]}")
    _code, logs, _err = _ssh_exec(ssh, "journalctl -u lima-router -n 25 --no-pager")
    if logs:
        print(logs)
    return False


def _poll_ready(ssh: paramiko.SSHClient) -> bool:
    deadline = time.time() + READY_WAIT_SECONDS
    last_detail = ""
    while time.time() < deadline:
        if not _service_is_active(ssh):
            return False
        ready, last_detail = _ready_ready(ssh)
        if ready:
            return True
        time.sleep(READY_POLL_SECONDS)

    print(f"  readiness never became ready; last: {last_detail[:240]}")
    _code, logs, _err = _ssh_exec(ssh, "journalctl -u lima-router -n 25 --no-pager")
    if logs:
        print(logs)
    return False


def _print_startup_phases(ssh: paramiko.SSHClient) -> None:
    """Fetch and print /health startup phase timings after readiness succeeds."""
    code, out, _err = _ssh_exec(ssh, "curl -sS -m 10 http://127.0.0.1:8080/health")
    if code != 0:
        return
    try:
        payload = json.loads(out)
        phases = payload.get("startup", {}).get("phases", [])
        if not phases:
            return
        print("  startup phases:")
        for phase in phases:
            status = phase.get("status", "ok")
            detail = f" ({phase.get('detail')})" if phase.get("detail") else ""
            print(f"    - {phase['name']}: {phase['elapsed_ms']:.1f} ms [{status}]{detail}")
    except (json.JSONDecodeError, KeyError, TypeError):
        return


def restart_server(target: DeployTarget) -> bool:
    """Clear pycache, restart the systemd service, and wait for health + readiness."""
    ssh = _connect_ssh(target)
    try:
        if not _restart_service(ssh):
            return False
        if not _poll_health(ssh):
            return False
        if not _poll_ready(ssh):
            return False
        _print_startup_phases(ssh)
        return True
    finally:
        ssh.close()
