#!/usr/bin/env python3
"""Deploy provider-probe assets to the JDCloud secondary node."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import deploy_config  # noqa: E402
from scripts.deploy_common import (  # noqa: E402
    JDCLOUD_REMOTE_PROBE,
    JDCLOUD_SERVER,
    JDCLOUD_USER,
    KEY,
    configure_ssh_host_keys,
)
from scripts.deploy_unified_deploy import ensure_remote_dir  # noqa: E402


def _connect_jdcloud() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    configure_ssh_host_keys(ssh)
    password = deploy_config.jdcloud_password()
    try:
        ssh.connect(JDCLOUD_SERVER, username=JDCLOUD_USER, key_filename=KEY, timeout=20)
    except paramiko.SSHException:
        if not password:
            raise
        ssh.connect(JDCLOUD_SERVER, username=JDCLOUD_USER, password=password, timeout=20)
    return ssh


def _exec(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    _stdin, stdout, stderr = ssh.exec_command(command)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return code, out, err


def collect_probe_files(project_root: Path) -> list[tuple[Path, str]]:
    pairs: list[tuple[Path, str]] = []
    probe_src = project_root / "packages" / "provider-probe-offline" / "provider_probe"
    if probe_src.is_dir():
        for path in sorted(probe_src.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(probe_src).as_posix()
                # 上传到 /opt/lima-probe/provider_probe/ 子目录，使 `from provider_probe.xxx import` 能正常工作
                pairs.append((path, f"{JDCLOUD_REMOTE_PROBE}/provider_probe/{rel}"))
    jdcloud_dir = project_root / "deploy" / "jdcloud"
    for name in (
        "lima-probe-browser.service",
        "lima-probe.service",
        "lima-probe.timer",
        "lima-probe-push.service",
        "lima-probe-push.timer",
    ):
        local = jdcloud_dir / name
        if local.is_file():
            pairs.append((local, f"/etc/systemd/system/{name}"))
    for name in ("push_probe_results.py", "push_probe_results_utils.py"):
        local = jdcloud_dir / name
        if local.is_file():
            pairs.append((local, f"{JDCLOUD_REMOTE_PROBE}/{name}"))
    return pairs


def upload_probe_files(pairs: list[tuple[Path, str]], *, dry_run: bool) -> int:
    if dry_run:
        for local, remote in pairs:
            print(f"  WOULD UPLOAD: {local.as_posix()} -> {remote}")
        return len(pairs)

    ssh = _connect_jdcloud()
    sftp = ssh.open_sftp()
    uploaded = 0
    try:
        for local, remote in pairs:
            ensure_remote_dir(sftp, os.path.dirname(remote))
            sftp.put(str(local), remote)
            uploaded += 1
    finally:
        sftp.close()
        ssh.close()
    return uploaded


def restart_probe_services(*, dry_run: bool) -> bool:
    command = (
        "set -e; "
        "pip3 install --break-system-packages -q httpx fastapi uvicorn pydantic 2>&1 "
        "| grep -v \"WARNING: Running pip as the 'root' user\" || true; "
        "systemctl daemon-reload; "
        "systemctl enable lima-probe-browser.service lima-probe.timer; "
        "systemctl restart lima-probe-browser.service; "
        "systemctl start lima-probe.timer; "
        "for i in 1 2 3 4 5 6 7 8 9 10; do "
        "  if curl -sf http://127.0.0.1:8092/health; then break; fi; "
        "  sleep 2; "
        "done; "
        "if ! curl -sf http://127.0.0.1:8092/health; then "
        "  echo '--- service status ---'; "
        "  systemctl status lima-probe-browser.service --no-pager || true; "
        "  echo '--- recent logs ---'; "
        "  journalctl -u lima-probe-browser.service --no-pager -n 20 || true; "
        "  exit 1; "
        "fi"
    )
    if dry_run:
        print(f"  WOULD RUN: {command[:120]}...")
        return True

    ssh = _connect_jdcloud()
    try:
        code, out, err = _exec(ssh, command)
        if code != 0:
            print(f"JDCloud probe restart failed (exit {code}): {err or out}")
            return False
        if out:
            print(out)
        return True
    finally:
        ssh.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy provider-probe to JDCloud")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parent.parent
    pairs = collect_probe_files(project_root)
    if not pairs:
        print("No JDCloud probe files found")
        return 1

    print(f"Deploying {len(pairs)} probe files to {JDCLOUD_SERVER}...")
    uploaded = upload_probe_files(pairs, dry_run=args.dry_run)
    print(f"Uploaded: {uploaded}")

    if not restart_probe_services(dry_run=args.dry_run):
        return 1

    print(f"JDCloud probe deploy OK ({JDCLOUD_SERVER})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
