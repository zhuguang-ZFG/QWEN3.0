#!/usr/bin/env python3
"""Deploy Gewechat Docker + LiMa wechat sidecar on VPS."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
GEWE_DIR = "/opt/gewechat"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

SIDEcar_FILES = [
    "wechat_bridge/__init__.py",
    "wechat_bridge/lima_client.py",
    "wechat_bridge/gewechat_client.py",
    "wechat_bridge/callback_handler.py",
    "wechat_bridge/sidecar_server.py",
]


def _run(ssh: paramiko.SSHClient, cmd: str, timeout: float | None = None) -> str:
    _stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    try:
        out = stdout.read().decode("utf-8", errors="replace")
    except Exception:
        out = ""
    err = stderr.read().decode("utf-8", errors="replace")
    return (out + ("\n" + err if err.strip() else "")).strip()


def main() -> None:
    if not os.path.isfile(KEY):
        sys.exit(f"SSH key not found: {KEY}")

    base = Path(__file__).resolve().parent.parent
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username="root", key_filename=KEY, banner_timeout=30, timeout=60)

    print("=== 1. Upload wechat_bridge ===")
    sftp = ssh.open_sftp()
    try:
        sftp.mkdir(f"{REMOTE}/wechat_bridge")
    except OSError:
        pass
    for rel in SIDEcar_FILES:
        sftp.put(str(base / rel), f"{REMOTE}/{rel}")
        print(f"  uploaded {rel}")
    sftp.put(str(base / "scripts" / "wechat_joint_debug.py"), f"{REMOTE}/wechat_joint_debug.py")
    sftp.close()

    print("=== 2. Start Gewechat Docker ===")
    _run(ssh, f"mkdir -p {GEWE_DIR}/data")
    docker_cmd = (
        "docker ps -a --format '{{.Names}}' | grep -q '^gewe$' && "
        "docker start gewe 2>/dev/null || "
        "(docker pull registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest && "
        "docker tag registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest gewe && "
        f"docker run -d --name gewe --restart=always --privileged=true "
        f"-v {GEWE_DIR}/data:/root/temp -p 2531:2531 -p 2532:2532 "
        "gewe /usr/sbin/init)"
    )
    print(_run(ssh, docker_cmd, timeout=300))

    print("=== 3. Patch lima-router .env for sidecar ===")
    sftp = ssh.open_sftp()
    sftp.put(str(base / "scripts" / "_patch_sidecar_env_remote.py"), f"{REMOTE}/_patch_sidecar_env.py")
    sftp.close()
    print(_run(ssh, f"cd {REMOTE} && /usr/local/bin/python3.10 _patch_sidecar_env.py"))
    print(_run(ssh, "systemctl restart lima-wechat-sidecar"))
    time.sleep(2)

    print("=== 4. systemd lima-wechat-sidecar ===")
    unit = f"""[Unit]
Description=LiMa WeChat Sidecar
After=network.target docker.service lima-router.service

[Service]
Type=simple
WorkingDirectory={REMOTE}
EnvironmentFile={REMOTE}/.env
ExecStart=/usr/local/bin/python3.10 -m uvicorn wechat_bridge.sidecar_server:app --host 0.0.0.0 --port 9919
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    sftp = ssh.open_sftp()
    with sftp.file("/etc/systemd/system/lima-wechat-sidecar.service", "w") as f:
        f.write(unit)
    sftp.close()
    print(_run(ssh, "systemctl daemon-reload && systemctl enable lima-wechat-sidecar && systemctl restart lima-wechat-sidecar"))
    time.sleep(3)
    print(_run(ssh, "systemctl is-active lima-wechat-sidecar"))
    print(_run(ssh, "curl -sf http://127.0.0.1:9919/health || true"))
    print(_run(ssh, "ss -tlnp | grep -E '2531|9919' || true"))

    ssh.close()
    print("\nDone. Next: python scripts/wechat_joint_debug.py refresh-qr")


if __name__ == "__main__":
    main()
