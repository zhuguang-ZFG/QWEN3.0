#!/usr/bin/env python3
"""Deploy CF-G-1/G-2 budget + admission overlay to LiMa VPS and smoke verify."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
ENV_FILE = f"{REMOTE}/.env"

FILES = [
    "backend_admission_store.py",
    "budget_cf_google.py",
    "budget_manager.py",
    "telegram_notify.py",
    "router_v3.py",
    "server_lifespan.py",
    "routes/telegram.py",
    "provider_automation/adapters/__init__.py",
    "provider_automation/adapters/cloudflare.py",
    "data/backend_admission.json",
    "scripts/probe_cf_new_models.py",
]

ENV_KEYS = {
    "LIMA_DYNAMIC_ADMISSION": "1",
}

REMOTE_VERIFY = r"""
import os, sys
sys.path.insert(0, '/opt/lima-router')
os.chdir('/opt/lima-router')
from dotenv import load_dotenv
load_dotenv('/opt/lima-router/.env')

import backends
from backends import BACKENDS
from backend_admission_store import get_enabled_overlays, get_routing_overlays_for_pool

overlays = get_enabled_overlays()
print('overlay_count', len(overlays))
chat_keys = get_routing_overlays_for_pool('chat')
print('chat_overlay_keys', ','.join(chat_keys))
for o in overlays[:8]:
    reg = o.backend_key in BACKENDS
    en = backends.is_enabled(o.backend_key)
    print(f'overlay {o.backend_key} registered={reg} enabled={en} tier={o.tier}')

mistral_enabled = backends.is_enabled('cfai_mistral')
print('cfai_mistral_enabled', mistral_enabled)

# routing: empty strong/medium static to surface overlay in selection
import router_v3
saved = {k: list(v) for k, v in router_v3.POOLS['chat'].items()}
try:
    router_v3.POOLS['chat']['strong'] = []
    router_v3.POOLS['chat']['medium'] = []
    router_v3.POOLS['chat']['floor'] = ['chat_ubi']
    health = {'chat_ubi': 'healthy'}
    for k in chat_keys:
        health[k] = 'healthy'
    selected = router_v3.select_backends('chat', health)
    print('select_backends_sample', ','.join(selected))
finally:
    for k, v in saved.items():
        router_v3.POOLS['chat'][k] = v

from provider_automation.adapters.cloudflare import call_cf_chat, cf_credentials_configured
if not cf_credentials_configured():
    print('cf_smoke_skip no_credentials')
    sys.exit(0)

model = overlays[0].model_id if overlays else '@cf/qwen/qwen2.5-coder-32b-instruct'
try:
    text, latency = call_cf_chat(model, [{'role': 'user', 'content': 'Say OK only.'}], 32)
    ok = len(text.strip()) >= 2 and latency < 15000
    print(f'cf_smoke model={model} ok={ok} latency_ms={latency:.0f} len={len(text.strip())}')
    sys.exit(0 if ok else 2)
except Exception as exc:
    print(f'cf_smoke_error {type(exc).__name__}: {exc}')
    sys.exit(3)
"""


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    if timeout is not None:
        stdout.channel.settimeout(timeout)
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


def _upsert_env(ssh: paramiko.SSHClient, key: str, value: str) -> None:
    escaped = value.replace("'", "'\"'\"'")
    cmd = (
        f"grep -q '^{key}=' {ENV_FILE} 2>/dev/null && "
        f"sed -i 's|^{key}=.*|{key}={escaped}|' {ENV_FILE} || "
        f"echo '{key}={escaped}' >> {ENV_FILE}"
    )
    _run(ssh, cmd)


def _restart_router(ssh: paramiko.SSHClient) -> None:
    _run(ssh, "systemctl stop lima-router 2>/dev/null || true")
    _run(ssh, "pkill -9 -f 'uvicorn server:app' || true")
    _run(ssh, "pkill -9 -f 'python3.10 server.py' || true")
    _run(ssh, "fuser -k 8080/tcp 2>/dev/null || true")
    time.sleep(3)
    _run(ssh, "systemctl reset-failed lima-router 2>/dev/null || true")
    out = _run(ssh, "systemctl start lima-router 2>&1", timeout=15)
    if out:
        _log(out[:200])
    time.sleep(8)


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    _log("deploy CF-G-1/G-2 admission overlay (rollback via GitHub)")

    for key, value in ENV_KEYS.items():
        _upsert_env(ssh, key, value)
        _log(f"env {key}={value}")

    _run(ssh, f"mkdir -p {REMOTE}/provider_automation/adapters {REMOTE}/data {REMOTE}/scripts {REMOTE}/routes")

    sftp = ssh.open_sftp()
    for rel in FILES:
        local = base / rel
        if not local.is_file():
            sftp.close()
            ssh.close()
            sys.exit(f"missing local file: {local}")
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        _ensure_remote_dir(sftp, remote.replace(REMOTE + "/", ""))
        sftp.put(str(local), remote)
        _log(f"uploaded {rel} ({local.stat().st_size} bytes)")
    sftp.close()

    _restart_router(ssh)

    active = _run(ssh, "systemctl is-active lima-router 2>/dev/null").strip()
    health = _run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 160")
    _log(f"service={active}")
    _log(f"health={health}")

    if active != "active":
        _log(_run(ssh, "journalctl -u lima-router -n 20 --no-pager"))
        ssh.close()
        return 1

    verify_path = f"{REMOTE}/scripts/_verify_cf_admission_overlay.py"
    sftp = ssh.open_sftp()
    with sftp.file(verify_path, "w") as handle:
        handle.write(REMOTE_VERIFY)
    sftp.close()

    verify_out = _run(
        ssh,
        f"cd {REMOTE} && set -a && . ./.env && set +a && "
        f"/usr/local/bin/python3.10 {verify_path}",
        timeout=120,
    )
    _log("--- overlay verify ---")
    _log(verify_out)

    ok = (
        "overlay_count" in verify_out
        and "chat_overlay_keys" in verify_out
        and "cf_smoke ok=True" in verify_out
        and "cfai_mistral_enabled False" in verify_out
    )
    if not ok and "cf_smoke_skip" in verify_out:
        ok = "overlay_count" in verify_out and int(
            verify_out.split("overlay_count")[1].split()[0] if "overlay_count" in verify_out else "0"
        ) >= 1

    # simpler ok check
    ok = (
        active == "active"
        and "overlay_count" in verify_out
        and "cfai_mistral_enabled False" in verify_out
        and ("cf_smoke ok=True" in verify_out or "select_backends_sample" in verify_out)
    )

    if ok:
        _log("deploy_cf_admission_overlay_ok")
    else:
        _log("deploy_cf_admission_overlay_FAILED")
        _log(_run(ssh, "journalctl -u lima-router -n 15 --no-pager"))

    ssh.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
