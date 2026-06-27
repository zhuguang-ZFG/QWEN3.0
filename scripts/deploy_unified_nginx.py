"""Nginx config sync helper for unified VPS deploy."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import paramiko

from config import deploy_config
from scripts.deploy_common import KEY, SERVER, configure_ssh_host_keys

_REMOTE_CONF_PATH = "/etc/nginx/conf.d/chat.donglicao.com.conf"
_SOURCE_CONF_NAME = "_nginx_chat_temp.conf"


def _ssh_exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def _connect_ssh() -> paramiko.SSHClient:
    """Open an SSH connection to the deploy server using key or password fallback."""
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    password = deploy_config.deploy_pass()
    try:
        ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    except paramiko.SSHException:
        if not password:
            raise
        ssh.connect(SERVER, username="root", password=password, timeout=15)
    return ssh


def _backup_remote_conf(ssh: paramiko.SSHClient) -> str | None:
    """Create a timestamped backup of the remote nginx config."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = f"{_REMOTE_CONF_PATH}.bak-{timestamp}"
    code, _out, err = _ssh_exec(ssh, f"cp {_REMOTE_CONF_PATH} {backup_path}")
    if code != 0:
        print(f"  nginx config backup failed: {err}", file=sys.stderr)
        return None
    return backup_path


def _restore_backup(ssh: paramiko.SSHClient, backup_path: str) -> bool:
    """Restore nginx config from backup and reload."""
    code, _out, err = _ssh_exec(ssh, f"cp {backup_path} {_REMOTE_CONF_PATH} && nginx -t && systemctl reload nginx")
    if code != 0:
        print(f"  nginx rollback failed: {err}", file=sys.stderr)
        return False
    print("  nginx config rolled back and reloaded")
    return True


def _upload_conf(ssh: paramiko.SSHClient, local_path: Path) -> bool:
    """Upload the authoritative nginx config to the remote path."""
    sftp = ssh.open_sftp()
    try:
        sftp.put(str(local_path), _REMOTE_CONF_PATH)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  nginx config upload failed: {exc}", file=sys.stderr)
        return False
    finally:
        sftp.close()


def _test_and_reload(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    """Run nginx -t and reload if valid; return success and detail."""
    code, out, err = _ssh_exec(ssh, "nginx -t")
    if code != 0:
        return False, f"nginx -t failed: {err or out}"
    code, _out, err = _ssh_exec(ssh, "systemctl reload nginx")
    if code != 0:
        return False, f"nginx reload failed: {err}"
    return True, ""


def _verify_ready_probe(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    """Verify /health/ready is reachable via localhost after reload."""
    code, out, err = _ssh_exec(ssh, "curl -sS -m 10 http://127.0.0.1:8080/health/ready")
    if code != 0:
        return False, err or out or f"curl exit {code}"
    return True, out


def sync_nginx_config(*, dry_run: bool = False) -> bool:
    """Sync authoritative nginx config to VPS, reload, and verify readiness path.

    On validation failure the original remote config is restored from backup.
    """
    project_root = Path(__file__).resolve().parent.parent
    local_path = project_root / _SOURCE_CONF_NAME
    if not local_path.exists():
        print(f"  nginx source config not found: {local_path}", file=sys.stderr)
        return False

    print(f"Syncing nginx config ({_SOURCE_CONF_NAME})...")
    if dry_run:
        print(f"  WOULD UPLOAD: {local_path} -> {_REMOTE_CONF_PATH}")
        return True

    ssh = _connect_ssh()
    try:
        backup_path = _backup_remote_conf(ssh)
        if not backup_path:
            return False

        if not _upload_conf(ssh, local_path):
            return False

        ok, detail = _test_and_reload(ssh)
        if not ok:
            print(f"  {detail}", file=sys.stderr)
            _restore_backup(ssh, backup_path)
            return False

        ok, detail = _verify_ready_probe(ssh)
        if not ok:
            print(f"  readiness probe verification failed: {detail}", file=sys.stderr)
            _restore_backup(ssh, backup_path)
            return False

        print("  nginx config synced and /health/ready reachable")
        return True
    finally:
        ssh.close()
