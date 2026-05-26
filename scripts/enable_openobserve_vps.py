#!/usr/bin/env python3
"""Enable OpenObserve export on VPS + journal ship smoke (PE-C-2-3)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
OO_PW = os.environ.get("OPENOBSERVE_PASSWORD", "change-me-local")

FILES = [
    "observability/openobserve_sink.py",
    "observability/metrics.py",
    "observability/events.py",
    "scripts/ship_lima_journal_openobserve.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 120) -> tuple[int, str]:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace").strip()
    return stdout.channel.recv_exit_status(), out


def _ensure_env(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    _run(
        ssh,
        f"grep -q '^{key}=' {REMOTE}/.env 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={value}|' {REMOTE}/.env || "
        f"echo '{key}={value}' >> {REMOTE}/.env",
    )


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parents[1]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
    _run(ssh, f"mkdir -p {REMOTE}/observability")

    for rel in FILES:
        local = base / rel
        sftp = ssh.open_sftp()
        sftp.put(str(local), f"{REMOTE}/{rel.replace(chr(92), '/')}")
        sftp.close()
        print(f"uploaded {rel}")

    for key, val in (
        ("OPENOBSERVE_ENABLED", "1"),
        ("OPENOBSERVE_URL", "http://127.0.0.1:5080"),
        ("OPENOBSERVE_ORG", "default"),
        ("OPENOBSERVE_STREAM", "lima_events"),
        ("OPENOBSERVE_JOURNAL_STREAM", "lima_journal"),
        ("OPENOBSERVE_USER", "root@example.com"),
        ("OPENOBSERVE_PASSWORD", OO_PW),
    ):
        _ensure_env(ssh, key, val)
        print(f"env {key}=...")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)

    export_test = _run(
        ssh,
        f"cd {REMOTE} && OPENOBSERVE_ENABLED=1 OPENOBSERVE_PASSWORD='{OO_PW}' "
        "/usr/local/bin/python3.10 -c \""
        "from observability.events import backend_error_event; "
        "from observability.openobserve_sink import post_records, event_to_record; "
        "e=backend_error_event('oo-smoke-req','google_flash_lite','rate_limited',1.0); "
        "ok=post_records([event_to_record(e)]); print('export_ok' if ok else 'export_FAIL')"
        "\"",
        timeout=60,
    )
    print(f"export_test={export_test[1][:120]}")

    journal = _run(
        ssh,
        f"cd {REMOTE} && OPENOBSERVE_ENABLED=1 OPENOBSERVE_PASSWORD='{OO_PW}' "
        "OPENOBSERVE_USER=root@example.com "
        "OPENOBSERVE_JOURNAL_STREAM=lima_journal "
        "/usr/local/bin/python3.10 scripts/ship_lima_journal_openobserve.py "
        "--since '2 hours ago' --limit 100",
        timeout=120,
    )
    print(f"journal_ship={journal[1][-300:]}")

    active = _run(ssh, "systemctl is-active lima-router")[1]
    ssh.close()
    journal_ok = "ship_ok" in journal[1]
    ok = active.strip() == "active" and "export_ok" in export_test[1] and journal_ok
    print("enable_openobserve_ok" if ok else "enable_openobserve_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
