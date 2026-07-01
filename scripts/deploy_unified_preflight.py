"""Remote capacity check, backup, and deploy preflight for unified VPS deploy."""

from __future__ import annotations

import shlex
import time

from config import deploy_config

from scripts.deploy_unified_common import (
    DEFAULT_MIN_FREE_MB,
    DEFAULT_MIN_MEM_MB,
    DeployTarget,
    _connect_ssh,
    _exec,
    _safe_backup_label,
    capacity_result,
    parse_capacity_output,
)


def check_remote_capacity(ssh, target: DeployTarget) -> dict[str, int]:
    command = (
        "set -eu; "
        f"disk=$(df -Pm {shlex.quote(target.remote_path)} | awk 'NR==2 {{print $4}}'); "
        "mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo); "
        'echo "disk_free_mb=$disk"; '
        'echo "mem_available_mb=$mem"'
    )
    code, out, err = _exec(ssh, command)
    if code != 0:
        raise RuntimeError(f"remote capacity check failed: {err or out}")
    capacity = parse_capacity_output(out)
    if "disk_free_mb" not in capacity or "mem_available_mb" not in capacity:
        raise RuntimeError(f"remote capacity check returned incomplete data: {out}")
    return capacity


def create_remote_backup(ssh, files: list[str], *, target: DeployTarget, label: str) -> str:
    safe_label = _safe_backup_label(label)
    backup_dir = f"{target.remote_path}/backups/{safe_label}-{time.strftime('%Y%m%d_%H%M%S')}"
    backup_file = f"{backup_dir}/runtime-before.tgz"
    command = (
        "set -eu; "
        f"mkdir -p {shlex.quote(backup_dir)}; "
        f"cd {shlex.quote(target.remote_path)}; "
        f"tar --ignore-failed-read -czf {shlex.quote(backup_file)} -T -; "
        f"echo {shlex.quote(backup_file)}"
    )
    stdin, stdout, stderr = ssh.exec_command(command)
    stdin.write("\n".join(files))
    stdin.channel.shutdown_write()
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if code != 0:
        raise RuntimeError(f"remote backup failed: {err or out}")
    return out.splitlines()[-1].strip()


def prepare_remote_deploy(files: list[str], *, target: DeployTarget, label: str) -> dict[str, object]:
    min_free_mb = deploy_config.deploy_min_free_mb()
    min_mem_mb = deploy_config.deploy_min_mem_mb()
    ssh = _connect_ssh(target)
    try:
        capacity = check_remote_capacity(ssh, target)
        result = capacity_result(
            capacity,
            min_free_mb=min_free_mb,
            min_mem_mb=min_mem_mb,
        )
        if not result["ok"]:
            return {"ok": False, "capacity": capacity, "reason": result["reason"]}
        backup_path = create_remote_backup(ssh, files, target=target, label=label)
        return {
            "ok": True,
            "capacity": capacity,
            "backup_path": backup_path,
        }
    finally:
        ssh.close()


def restore_remote_backup(backup_path: str, *, target: DeployTarget) -> bool:
    """Extract a pre-deploy tar backup back into the target remote path."""
    if not backup_path:
        return False
    ssh = _connect_ssh(target)
    try:
        command = (
            "set -eu; "
            f"test -f {shlex.quote(backup_path)}; "
            f"cd {shlex.quote(target.remote_path)}; "
            f"tar -xzf {shlex.quote(backup_path)}"
        )
        code, out, err = _exec(ssh, command)
        if code != 0:
            print(f"rollback failed: {err or out}")
            return False
        print(f"rollback restored from {backup_path}")
        return True
    finally:
        ssh.close()
