"""Remote capacity check, backup, and deploy preflight for unified VPS deploy."""

from __future__ import annotations

import shlex
import time

from config import deploy_config

from scripts.deploy_unified_common import (
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
        f"mkdir -p {shlex.quote(target.remote_path)}; "
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
    manifest_file = f"{backup_dir}/pre-state.tsv"
    list_file = f"{backup_dir}/present-files.txt"
    remote_env = f"{target.remote_path}/.env"
    service_file = "/etc/systemd/system/dlc-drawing.service"
    command = (
        "set -eu; "
        f"mkdir -p {shlex.quote(backup_dir)}; "
        f"cd {shlex.quote(target.remote_path)}; "
        f": > {shlex.quote(manifest_file)}; : > {shlex.quote(list_file)}; "
        "while IFS= read -r path; do "
        '[ -n "$path" ] || continue; '
        f'if [ -e "$path" ]; then printf \'present\\t%s\\n\' "$path" >> {shlex.quote(manifest_file)}; '
        f"printf '%s\\n' \"$path\" >> {shlex.quote(list_file)}; "
        f"else printf 'missing\\t%s\\n' \"$path\" >> {shlex.quote(manifest_file)}; fi; done; "
        f"tar -czf {shlex.quote(backup_file)} -T {shlex.quote(list_file)}; "
        f"if [ -f {shlex.quote(remote_env)} ]; then cp -p {shlex.quote(remote_env)} "
        f"{shlex.quote(backup_dir + '/runtime.env')}; else touch {shlex.quote(backup_dir + '/env.missing')}; fi; "
        f"if [ -f {shlex.quote(service_file)} ]; then cp -p {shlex.quote(service_file)} "
        f"{shlex.quote(backup_dir + '/service.unit')}; else touch {shlex.quote(backup_dir + '/service.missing')}; fi; "
        f"if [ ! -d {shlex.quote(target.remote_path + '/.venv')} ]; then "
        f"touch {shlex.quote(backup_dir + '/venv.missing')}; fi; "
        f"if [ -d {shlex.quote(target.remote_path + '/.venv.previous')} ]; then "
        f"mv -- {shlex.quote(target.remote_path + '/.venv.previous')} "
        f"{shlex.quote(backup_dir + '/venv-previous-predeploy')}; fi; "
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
    if not out:
        raise RuntimeError("remote backup returned no backup path")
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
    """Restore old files and remove paths that did not exist before deployment."""
    if not backup_path:
        return False
    ssh = _connect_ssh(target)
    try:
        backup_dir = backup_path.rsplit("/", 1)[0]
        manifest = shlex.quote(f"{backup_dir}/pre-state.tsv")
        env_backup = shlex.quote(f"{backup_dir}/runtime.env")
        env_missing = shlex.quote(f"{backup_dir}/env.missing")
        unit_backup = shlex.quote(f"{backup_dir}/service.unit")
        unit_missing = shlex.quote(f"{backup_dir}/service.missing")
        stale_venv = shlex.quote(f"{backup_dir}/venv-previous-predeploy")
        venv_missing = shlex.quote(f"{backup_dir}/venv.missing")
        remote_env = shlex.quote(f"{target.remote_path}/.env")
        current_venv = shlex.quote(f"{target.remote_path}/.venv")
        previous_venv = shlex.quote(f"{target.remote_path}/.venv.previous")
        next_venv = shlex.quote(f"{target.remote_path}/.venv.next")
        service_file = "/etc/systemd/system/dlc-drawing.service"
        command = (
            "set -eu; "
            f"test -f {shlex.quote(backup_path)}; "
            f"cd {shlex.quote(target.remote_path)}; "
            f"tar -xzf {shlex.quote(backup_path)}; "
            f"if [ -f {manifest} ]; then "
            f"awk -F '\\t' '$1 == \"missing\" {{print substr($0, index($0,$2))}}' {manifest} | "
            'while IFS= read -r path; do [ -n "$path" ] && rm -f -- "$path"; done; fi; '
            f"if [ -f {env_backup} ]; then install -m 0600 {env_backup} {remote_env}; "
            f"elif [ -f {env_missing} ]; then rm -f -- {remote_env}; fi; "
            f"if [ -f {unit_backup} ]; then install -m 0644 {unit_backup} {shlex.quote(service_file)}; "
            f"elif [ -f {unit_missing} ]; then rm -f -- {shlex.quote(service_file)}; fi; "
            f"if [ -d {previous_venv} ]; then rm -rf -- {current_venv}; mv -- {previous_venv} {current_venv}; fi; "
            f"if [ -f {venv_missing} ] && [ ! -d {previous_venv} ]; then rm -rf -- {current_venv}; fi; "
            f"if [ -d {stale_venv} ]; then rm -rf -- {previous_venv}; mv -- {stale_venv} {previous_venv}; fi; "
            f"rm -rf -- {next_venv}; systemctl daemon-reload"
        )
        code, out, err = _exec(ssh, command)
        if code != 0:
            print(f"rollback failed: {err or out}")
            return False
        print(f"rollback restored from {backup_path}")
        return True
    finally:
        ssh.close()
