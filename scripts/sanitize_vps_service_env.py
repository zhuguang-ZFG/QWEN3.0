#!/usr/bin/env python3
"""Remove secret-bearing Environment lines from the VPS systemd unit."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy_common import KEY, SERVER, configure_ssh_host_keys

SERVICE_PATH = "/etc/systemd/system/lima-router.service"
SECRET_ENV_PREFIXES = (
    "Environment=LIMA_API_KEY=",
    "Environment=LIMA_API_KEYS=",
)


def sanitize_unit_text(text: str) -> tuple[str, int]:
    removed = 0
    lines: list[str] = []
    for line in text.splitlines():
        if any(line.startswith(prefix) for prefix in SECRET_ENV_PREFIXES):
            removed += 1
            continue
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n", removed


def _read_file(sftp: paramiko.SFTPClient, path: str) -> str:
    with sftp.file(path, "r") as handle:
        return handle.read().decode("utf-8", errors="replace")


def _write_file(sftp: paramiko.SFTPClient, path: str, text: str) -> None:
    with sftp.file(path, "w") as handle:
        handle.write(text.encode("utf-8"))


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 60) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    detail = "\n".join(part for part in (out, err) if part)
    return code, detail


def sanitize_remote_service(*, dry_run: bool = False) -> dict[str, object]:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=15)
    backup = f"{SERVICE_PATH}.bak.{time.strftime('%Y%m%d%H%M%S')}"
    try:
        sftp = ssh.open_sftp()
        try:
            original = _read_file(sftp, SERVICE_PATH)
            sanitized, removed = sanitize_unit_text(original)
            if dry_run or removed == 0:
                return {"changed": False, "removed": removed, "backup": ""}
            code, detail = _run(ssh, f"cp {SERVICE_PATH} {backup}")
            if code != 0:
                raise RuntimeError(f"backup failed: {detail}")
            _write_file(sftp, SERVICE_PATH, sanitized)
        finally:
            sftp.close()

        for cmd in ("systemctl daemon-reload", "systemctl restart lima-router"):
            code, detail = _run(ssh, cmd)
            if code != 0:
                raise RuntimeError(f"{cmd} failed: {detail}")
        code, health = _run(ssh, "curl -sS -m 5 http://127.0.0.1:8080/health", timeout=15)
        return {
            "changed": True,
            "removed": removed,
            "backup": backup,
            "health_ok": code == 0 and "ok" in health,
        }
    finally:
        ssh.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sanitize_remote_service(dry_run=args.dry_run)
    print(result)
    return 0 if result.get("health_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
