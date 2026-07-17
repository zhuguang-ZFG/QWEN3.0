"""Paramiko SSH connect/exec helpers for unified VPS deploy."""

from __future__ import annotations

import os

import paramiko

from scripts.deploy_common import configure_ssh_host_keys
from scripts.deploy_unified_common import DeployTarget


def connect_ssh(target: DeployTarget) -> paramiko.SSHClient:
    """Open SSH via key and/or password; keepalive avoids SFTP idle disconnect."""
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    connect_kw = {
        "hostname": target.host,
        "username": target.user,
        "timeout": 15,
        "allow_agent": False,
        "look_for_keys": False,
    }
    key_path = target.key_path if target.key_path and os.path.exists(target.key_path) else None
    if key_path and target.password:
        try:
            ssh.connect(key_filename=key_path, **connect_kw)
        except paramiko.AuthenticationException:
            ssh.connect(password=target.password, **connect_kw)
    elif target.password:
        ssh.connect(password=target.password, **connect_kw)
    elif key_path:
        ssh.connect(key_filename=key_path, **connect_kw)
    else:
        raise paramiko.SSHException("no SSH key or password configured for deploy")
    transport = getattr(ssh, "get_transport", lambda: None)()
    if transport is not None:
        transport.set_keepalive(15)
    return ssh


def exec_ssh(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


# Back-compat aliases for internal importers/tests
_connect_ssh = connect_ssh
_exec = exec_ssh
