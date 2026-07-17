"""Service restart and health-polling for unified VPS deploy.

Post-P5 slimdown: the retired lima-router (:8080) is no longer restarted.
The deploy now targets the dlc-drawing service (:8081).
"""

from __future__ import annotations

import json
import io
import re
import shlex
import time
from pathlib import Path

from scripts.deploy_common import configure_ssh_host_keys  # noqa: F401 — re-export for older tests
from scripts.deploy_unified_common import (
    HEALTH_GRACE_AFTER_RESTART_S,
    HEALTH_POLL_SECONDS,
    HEALTH_WAIT_SECONDS,
    DeployTarget,
)
from scripts.deploy_unified_ssh import _connect_ssh, _ssh_exec
import paramiko  # noqa: F401 — tests patch restart_mod.paramiko for historical fixtures

_SERVICE = "dlc-drawing"
_HEALTH_URL = "http://127.0.0.1:8081/health/ready"
_ENV_LINE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
_PIP_TIMEOUT_S = 900


def _merge_env_update(ssh: paramiko.SSHClient, target: DeployTarget, update_path: Path) -> bool:
    """Append only absent keys from a validated dotenv file."""
    try:
        raw_lines = update_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"env update read failed: {exc}")
        return False
    entries = [line for line in raw_lines if line and not line.startswith("#")]
    if any(not _ENV_LINE_RE.fullmatch(line) for line in entries):
        print("env update contains an invalid line; expected KEY=value")
        return False
    keys = [line.split("=", 1)[0] for line in entries]
    if len(keys) != len(set(keys)):
        print("env update contains duplicate keys")
        return False
    remote_env = f"{target.remote_path}/.env"
    remote_update = f"{target.remote_path}/.env.deploy-update"
    sftp = None
    try:
        sftp = ssh.open_sftp()
        sftp.putfo(io.BytesIO(("\n".join(entries) + "\n").encode()), remote_update)
    except Exception as exc:
        print(f"env update upload failed: {exc}")
        return False
    finally:
        if sftp is not None:
            sftp.close()
    command = (
        "set -eu; "
        f"trap 'rm -f -- {shlex.quote(remote_update)}' EXIT; "
        f"touch {shlex.quote(remote_env)}; chmod 0600 {shlex.quote(remote_env)}; "
        f"while IFS= read -r line; do key=${{line%%=*}}; "
        f'grep -q "^${{key}}=" {shlex.quote(remote_env)} || printf \'%s\\n\' "$line" >> {shlex.quote(remote_env)}; '
        f"done < {shlex.quote(remote_update)}"
    )
    code, _out, err = _ssh_exec(ssh, command)
    if code != 0:
        print(f"env update merge failed: {err}")
        return False
    return True


def _install_service_unit(ssh: paramiko.SSHClient) -> bool:
    service_local = Path(__file__).resolve().parents[1] / "deploy/aliyun/dlc-drawing.service"
    service_remote = f"/etc/systemd/system/{_SERVICE}.service"
    service_next = f"{service_remote}.next"
    if not service_local.exists():
        print(f"local service file not found: {service_local}")
        return False
    sftp = None
    try:
        sftp = ssh.open_sftp()
        sftp.put(str(service_local), service_next)
    except Exception as exc:
        print(f"service file upload failed: {exc}")
        return False
    finally:
        if sftp is not None:
            sftp.close()
    command = f"install -m 0644 {shlex.quote(service_next)} {shlex.quote(service_remote)} && rm -f {shlex.quote(service_next)}"
    code, _out, err = _ssh_exec(ssh, command)
    if code != 0:
        print(f"service file install failed: {err}")
        return False
    return True


def _prepare_dependencies(ssh: paramiko.SSHClient, target: DeployTarget) -> bool:
    root = shlex.quote(target.remote_path)
    current = shlex.quote(f"{target.remote_path}/.venv")
    next_venv = shlex.quote(f"{target.remote_path}/.venv.next")
    previous = shlex.quote(f"{target.remote_path}/.venv.previous")
    requirements = shlex.quote(f"{target.remote_path}/requirements_server.txt")
    command = (
        f"set -eu; cd {root}; hash=$(sha256sum {requirements} | awk '{{print $1}}'); "
        f"if [ -x {current}/bin/python ] && [ -f {current}/.lima-requirements.sha256 ] && "
        f'grep -qx "$hash" {current}/.lima-requirements.sha256; then exit 0; fi; '
        f"rm -rf -- {next_venv}; python3 -m venv {next_venv}; "
        f"{next_venv}/bin/python -m pip install -r {requirements}; {next_venv}/bin/python -m pip check; "
        f"{next_venv}/bin/python -c 'import fastapi, uvicorn'; printf '%s\\n' \"$hash\" > {next_venv}/.lima-requirements.sha256; "
        f"rm -rf -- {previous}; "
        f"if [ -d {current} ]; then mv -- {current} {previous}; fi; mv -- {next_venv} {current}"
    )
    print("Preparing runtime dependencies (hash short-circuit or pip)...")
    code, _out, err = _ssh_exec(ssh, command, timeout=_PIP_TIMEOUT_S)
    if code == 0:
        return True
    # Pip/network flakes must not brick deploys when the current venv still imports.
    probe = f"{current}/bin/python -c 'import fastapi, uvicorn'"
    probe_code, _probe_out, _probe_err = _ssh_exec(ssh, probe, timeout=30)
    if probe_code == 0:
        print(f"dependency prepare failed; keeping existing venv ({err[:200]})")
        return True
    print(f"dependency preparation failed: {err}")
    return False


def _prepare_service(
    ssh: paramiko.SSHClient,
    target: DeployTarget,
    *,
    env_update: Path | None,
) -> bool:
    """Ensure dlc-drawing service is installed and the runtime dir has a .env.

    Post-P5: the new service uses a separate WorkingDirectory (/opt/dlc-drawing).
    If this is the first deploy, copy .env from the legacy /opt/lima-router
    directory instead of overwriting it.
    """
    legacy_env = "/opt/lima-router/.env"
    code, _out, err = _ssh_exec(ssh, f"mkdir -p {shlex.quote(target.remote_path)}")
    if code != 0:
        print(f"mkdir remote path failed: {err}")
        return False

    code, _out, err = _ssh_exec(
        ssh,
        f"if [ -f {legacy_env} ] && [ ! -f {shlex.quote(target.remote_path + '/.env')} ]; then cp {legacy_env} {shlex.quote(target.remote_path + '/.env')}; fi",
    )
    if code != 0:
        print(f".env setup failed: {err}")
        return False

    if env_update is not None and not _merge_env_update(ssh, target, env_update):
        return False
    if not _install_service_unit(ssh):
        return False
    if not _prepare_dependencies(ssh, target):
        return False

    code, _out, err = _ssh_exec(ssh, "systemctl daemon-reload")
    if code != 0:
        print(f"daemon-reload failed: {err}")
        return False

    return True


def _restart_service(ssh: paramiko.SSHClient) -> bool:
    code, _out, err = _ssh_exec(ssh, f"systemctl restart {_SERVICE}")
    if code != 0:
        print(f"restart command failed: {err}")
        return False
    if HEALTH_GRACE_AFTER_RESTART_S > 0:
        time.sleep(HEALTH_GRACE_AFTER_RESTART_S)
    return True


def _service_is_active(ssh: paramiko.SSHClient) -> bool:
    active_code, _active_out, _active_err = _ssh_exec(ssh, f"systemctl is-active {_SERVICE}")
    if active_code != 0:
        print(f"  service not active (is-active exit {active_code}); fetching logs...")
        _code, logs, _err = _ssh_exec(ssh, f"journalctl -u {_SERVICE} -n 25 --no-pager")
        if logs:
            print(logs)
        return False
    return True


def _health_ok(ssh: paramiko.SSHClient) -> tuple[bool, str]:
    """Poll the authoritative readiness endpoint on :8081."""
    code, out, err = _ssh_exec(ssh, f"curl -sS -m 30 {_HEALTH_URL}")
    last_detail = out or err or f"curl exit {code}"
    if code == 0:
        try:
            payload = json.loads(out)
            if payload.get("status") == "ok":
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
        ok, last_detail = _health_ok(ssh)
        if ok:
            return True
        time.sleep(HEALTH_POLL_SECONDS)

    print(f"  health never became ready; last: {last_detail[:240]}")
    _code, logs, _err = _ssh_exec(ssh, f"journalctl -u {_SERVICE} -n 25 --no-pager")
    if logs:
        print(logs)
    return False


def _print_health(ssh: paramiko.SSHClient) -> None:
    """Fetch and print /health payload after the service is healthy."""
    code, out, _err = _ssh_exec(ssh, f"curl -sS -m 10 {_HEALTH_URL}")
    if code == 0:
        print(f"  health: {out[:200]}")


def restart_server(
    target: DeployTarget,
    *,
    prepare: bool = True,
    env_update: Path | None = None,
) -> bool:
    """Restart dlc-drawing and wait for readiness, optionally preparing runtime state."""
    ssh = _connect_ssh(target)
    try:
        if prepare and not _prepare_service(
            ssh,
            target,
            env_update=env_update,
        ):
            return False
        if not _restart_service(ssh):
            return False
        if not _poll_health(ssh):
            return False
        _print_health(ssh)
        return True
    finally:
        ssh.close()
