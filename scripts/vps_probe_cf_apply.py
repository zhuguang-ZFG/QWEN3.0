#!/usr/bin/env python3
"""Run CF probe on VPS, apply overlays, restart router, and smoke verify."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
PROBE_LIMIT = int(os.environ.get("CF_PROBE_LIMIT", "0"))
TARGET_OVERLAYS = int(os.environ.get("CF_TARGET_OVERLAYS", "30"))


UPLOAD = [
    "backend_admission_store.py",
    "provider_automation/__init__.py",
    "provider_automation/catalog.py",
    "provider_automation/probe.py",
    "provider_automation/runner.py",
    "provider_automation/adapters/__init__.py",
    "provider_automation/adapters/cloudflare.py",
    "provider_inventory/__init__.py",
    "provider_inventory/cloudflare.py",
    "provider_inventory/compare.py",
    "provider_inventory/google.py",
    "data/cf_model_inventory.json",
    "scripts/inventory_cloudflare_models.py",
    "scripts/probe_cf_new_models.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float = 600) -> tuple[int, str]:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    return o.channel.recv_exit_status(), out.strip()


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _run(ssh, f"mkdir -p {REMOTE}/provider_automation/adapters {REMOTE}/provider_inventory {REMOTE}/data {REMOTE}/scripts")

    sftp = ssh.open_sftp()
    for rel in UPLOAD:
        local = base / rel
        if not local.is_file():
            _log(f"skip missing {rel}")
            continue
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        sftp.put(str(local), remote)
        _log(f"uploaded {rel}")
    sftp.close()

    inv_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/inventory_cloudflare_models.py"
    )
    _log("refreshing CF inventory on VPS...")
    code_inv, inv_out = _run(ssh, inv_cmd, timeout=120)
    _log(inv_out[:300] if inv_out else f"inventory exit={code_inv}")

    limit_flag = f"--limit {PROBE_LIMIT}" if PROBE_LIMIT > 0 else ""
    probe_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 scripts/probe_cf_new_models.py "
        f"{limit_flag} --target-overlays {TARGET_OVERLAYS} --apply".replace("  ", " ")
    )
    _log(f"running probe target_overlays={TARGET_OVERLAYS} (may take several minutes)...")
    code, out = _run(ssh, probe_cmd, timeout=900)
    _log(out)
    if code != 0:
        _log(f"probe exit code={code}")

    _run(ssh, "systemctl restart lima-router")
    time.sleep(8)
    active = _run(ssh, "systemctl is-active lima-router")[1]
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 120")[1]

    verify_cmd = (
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 -c \""
        f"import os; os.chdir('{REMOTE}'); "
        f"from backend_admission_store import get_enabled_overlays; "
        f"from backends import BACKENDS; "
        f"o=get_enabled_overlays(); "
        f"print('overlay_total', len(o)); "
        f"print('registered', sum(1 for x in o if x.backend_key in BACKENDS));"
        f"print('keys', ','.join(x.backend_key for x in o));"
        f"\""
    )
    _, verify = _run(ssh, verify_cmd, timeout=60)
    _log("--- post-probe ---")
    _log(f"service={active}")
    _log(f"health={health}")
    _log(verify)

    ssh.close()
    ok = active == "active" and "overlay_total" in verify
    _log("vps_cf_probe_apply_ok" if ok else "vps_cf_probe_apply_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
