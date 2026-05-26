#!/usr/bin/env python3
"""Deploy TG-GH-1 / INF-B reliability ops slice to LiMa VPS and smoke verify."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

FILES = [
    "telegram_notify.py",
    "telegram_outbound.py",
    "telegram_push_translate.py",
    "healthcheck_ping.py",
    "healthchecks_io.py",
    "scripts/smoke_telegram_outbound.py",
    "scripts/healthcheck_ping.py",
    "scripts/vps_router_healthcheck.sh",
    "scripts/deploy_healthchecks_vps.py",
    "scripts/gitee_mirror_status.py",
    "gitee_mirror.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = 60) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        out = (out + "\n" + err).strip()
    return out


def _log(msg: str) -> None:
    print(msg, flush=True)


def _ensure_remote_dir(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    parts = remote_path.replace("\\", "/").split("/")
    cur = ""
    for part in parts[:-1]:
        if not part:
            continue
        cur = f"{cur}/{part}" if cur else part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def _restart_router(ssh: paramiko.SSHClient) -> None:
    _run(ssh, "systemctl stop lima-router 2>/dev/null || true")
    _run(ssh, "pkill -9 -f 'uvicorn server:app' || true")
    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(3)
    _run(ssh, "systemctl reset-failed lima-router 2>/dev/null || true")
    _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    time.sleep(8)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("deploy reliability ops (TG-GH-1 / INF-B scripts)")
    _run(ssh, f"mkdir -p {REMOTE}/scripts")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _ensure_remote_dir(sftp, remote)
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")
    sftp.close()

    _restart_router(ssh)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 200")
    _log(f"service={active}")
    _log(f"health={health}")

    smoke_out = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/smoke_telegram_outbound.py",
        timeout=45,
    )
    _log("--- telegram outbound smoke ---")
    _log(smoke_out)

    hc_out = _run(
        ssh,
        f"cd {REMOTE} && /usr/local/bin/python3.10 scripts/healthcheck_ping.py --dry-run",
        timeout=20,
    )
    _log("--- healthcheck dry-run ---")
    _log(hc_out)

    ok = active == "active" and ("health" in health.lower() or '"status"' in health)
    tg_ok = smoke_out.strip().startswith("OK:")

    if ok and tg_ok:
        _log("deploy_reliability_ops_ok")
    else:
        _log("deploy_reliability_ops_PARTIAL")
        if not tg_ok:
            _log("telegram smoke did not pass — check FRP 7897 / TELEGRAM_BOT_TOKEN")

    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
