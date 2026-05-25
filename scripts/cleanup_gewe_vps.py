#!/usr/bin/env python3
"""Retire GeWe/Gewechat VPS stack (9919 sidecar + 2531 Docker). iLink bridge unchanged."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

GEWE_ENV_KEYS = (
    "GEWECHAT_BASE_URL",
    "GEWECHAT_TOKEN",
    "GEWECHAT_APP_ID",
    "GEWECHAT_REGION_ID",
    "GEWECHAT_CALLBACK_URL",
    "WECHAT_SIDECAR_HOST",
    "WECHAT_SIDECAR_PORT",
)

REMOTE_GEWE_FILES = (
    f"{REMOTE}/chat.donglicao.com.wechat-sidecar.snippet.conf",
    f"{REMOTE}/_nginx_patch_wechat_remote.py",
    f"{REMOTE}/_nginx_unpatch_wechat_remote.py",
    f"{REMOTE}/_patch_geweapi_env_remote.py",
    f"{REMOTE}/_vps_refresh_qr_remote.py",
    f"{REMOTE}/wechat_joint_debug.py",
    f"{REMOTE}/data/wechat_gewechat_state.json",
    f"{REMOTE}/data/wechat_login_qr.html",
    f"{REMOTE}/wechat_bridge/sidecar_server.py",
    f"{REMOTE}/wechat_bridge/gewechat_client.py",
    f"{REMOTE}/wechat_bridge/callback_handler.py",
)


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _i, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read() + e.read()).decode("utf-8", errors="replace").strip()


def _patch_env_remove_gewe(ssh: paramiko.SSHClient) -> None:
    py = f'''
from pathlib import Path
p = Path("{REMOTE}/.env")
if not p.exists():
    print("env_missing")
    raise SystemExit(0)
lines = p.read_text(encoding="utf-8").splitlines()
drop = {repr(set(GEWE_ENV_KEYS))}
out = []
for line in lines:
    if "=" in line and not line.strip().startswith("#"):
        k = line.split("=", 1)[0].strip()
        if k in drop:
            continue
    out.append(line)
p.write_text("\\n".join(out) + "\\n", encoding="utf-8")
print("env_gewe_removed")
'''
    sftp = ssh.open_sftp()
    sftp.file(f"{REMOTE}/_strip_gewe_env.py", "w").write(py.encode("utf-8"))
    sftp.close()
    print(_run(ssh, f"cd {REMOTE} && python3.10 _strip_gewe_env.py && rm -f _strip_gewe_env.py"))


def main() -> int:
    dry = "--dry-run" in sys.argv
    if not os.path.isfile(KEY):
        print(f"SSH key missing: {KEY}")
        return 1

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)

    steps = [
        ("stop sidecar", "systemctl stop lima-wechat-sidecar 2>/dev/null || true"),
        ("disable sidecar", "systemctl disable lima-wechat-sidecar 2>/dev/null || true"),
        ("remove unit", "rm -f /etc/systemd/system/lima-wechat-sidecar.service"),
        ("daemon-reload", "systemctl daemon-reload"),
        ("stop gewe docker", "docker stop gewe 2>/dev/null || true"),
        ("rm gewe docker", "docker rm gewe 2>/dev/null || true"),
        ("ports check", "ss -tlnp | grep -E ':9919|:2531' || echo ports_free"),
    ]

    if dry:
        for name, cmd in steps:
            print(f"[dry] {name}: {cmd}")
        ssh.close()
        return 0

    for name, cmd in steps:
        print(f"=== {name} ===")
        print(_run(ssh, cmd))

    _patch_env_remove_gewe(ssh)

    sftp = ssh.open_sftp()
    sftp.put(
        str(base / "scripts/_nginx_unpatch_wechat_remote.py"),
        f"{REMOTE}/_nginx_unpatch_wechat_remote.py",
    )
    sftp.close()
    print("=== nginx unpatch ===")
    out = _run(ssh, f"python3.10 {REMOTE}/_nginx_unpatch_wechat_remote.py 2>&1")
    print(out)
    if "nginx_unpatched" in out or "nginx_already_clean" in out:
        print(_run(ssh, "nginx -t 2>&1 && systemctl reload nginx"))

    print("=== remove remote gewe artifacts ===")
    for path in REMOTE_GEWE_FILES:
        print(_run(ssh, f"rm -f {path}"))

    print("=== lima-router still active (iLink channel only) ===")
    print(_run(ssh, "systemctl is-active lima-router"))
    print(_run(ssh, "curl -sf http://127.0.0.1:8080/health | head -c 120"))
    print(_run(ssh, "ss -tlnp | grep -E ':9919|:2531' || echo gewe_ports_closed"))

    ssh.close()
    print("cleanup_gewe_vps done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
