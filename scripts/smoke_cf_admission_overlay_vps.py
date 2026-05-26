#!/usr/bin/env python3
"""Post-deploy VPS smoke for CF admission overlay."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

SERVER = "47.112.162.80"
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

VERIFY = r"""
import os, sys
sys.path.insert(0, '/opt/lima-router')
os.chdir('/opt/lima-router')
from dotenv import load_dotenv
load_dotenv('/opt/lima-router/.env')

import backends
from backends import BACKENDS
from backend_admission_store import get_enabled_overlays, get_routing_overlays_for_pool, apply_startup

apply_startup()
overlays = get_enabled_overlays()
print('overlay_count', len(overlays))
chat_keys = get_routing_overlays_for_pool('chat')
print('chat_overlay_keys', ','.join(chat_keys))
for o in overlays:
    print('overlay', o.backend_key, 'registered=', o.backend_key in BACKENDS, 'tier=', o.tier)
print('cfai_mistral_enabled', backends.is_enabled('cfai_mistral'))

import router_v3
saved = {k: list(v) for k, v in router_v3.POOLS['chat'].items()}
try:
    router_v3.POOLS['chat']['strong'] = []
    router_v3.POOLS['chat']['medium'] = []
    router_v3.POOLS['chat']['floor'] = ['chat_ubi']
    health = {'chat_ubi': 'healthy', **{k: 'healthy' for k in chat_keys}}
    selected = router_v3.select_backends('chat', health)
    print('select_backends_sample', ','.join(selected))
finally:
    for k, v in saved.items():
        router_v3.POOLS['chat'][k] = v

from provider_automation.adapters.cloudflare import call_cf_chat, cf_credentials_configured
if not cf_credentials_configured():
    print('cf_smoke_skip no_credentials')
    sys.exit(0)

model = '@cf/qwen/qwen2.5-coder-32b-instruct'
text, latency = call_cf_chat(model, [{'role': 'user', 'content': 'Say OK only.'}], 32)
print('cf_qwen_coder_smoke ok=', len(text.strip()) >= 2 and latency < 15000, 'latency_ms=', int(latency))

if overlays:
    om = overlays[0].model_id
    text2, latency2 = call_cf_chat(om, [{'role': 'user', 'content': 'Say OK only.'}], 32)
    print('cf_overlay_smoke model=', om, 'ok=', len(text2.strip()) >= 2 and latency2 < 15000, 'latency_ms=', int(latency2))
"""


def main() -> int:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    health_cmd = "curl -sf http://127.0.0.1:8080/health | head -c 120"
    _i, o, e = ssh.exec_command(health_cmd, timeout=30)
    health = (o.read() + e.read()).decode("utf-8", "replace").strip()
    print("health:", health)

    verify_path = f"{REMOTE}/scripts/_verify_cf_admission_overlay.py"
    sftp = ssh.open_sftp()
    with sftp.file(verify_path, "w") as handle:
        handle.write(VERIFY)
    sftp.close()

    cmd = f"cd {REMOTE} && set -a && . ./.env && set +a && /usr/local/bin/python3.10 {verify_path}"
    _i, o, e = ssh.exec_command(cmd, timeout=120)
    out = (o.read() + e.read()).decode("utf-8", "replace")
    print(out)

    ssh.close()
    ok = (
        "overlay_count" in out
        and "cfai_mistral_enabled False" in out
        and ("cf_qwen_coder_smoke ok= True" in out or "cf_qwen_coder_smoke ok=True" in out)
        and ("cf_overlay_smoke" in out and "ok= True" in out or "ok=True" in out)
    )
    print("smoke_cf_admission_overlay_ok" if ok else "smoke_cf_admission_overlay_FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
