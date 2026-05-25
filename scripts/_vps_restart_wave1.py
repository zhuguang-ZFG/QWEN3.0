#!/usr/bin/env python3
import os
import time
import paramiko

SERVER = os.environ.get("LIMA_VPS_HOST", "47.112.162.80")
REMOTE = "/opt/lima-router"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER, username="root", key_filename=KEY, timeout=60)
ssh.exec_command("systemctl restart lima-router")
time.sleep(10)
for cmd in [
    "systemctl is-active lima-router",
    "curl -sf http://127.0.0.1:8080/health | head -c 100",
    f"grep -E 'LIMA_CHANNEL_VOICE|LIMA_CHANNEL_INVITE' {REMOTE}/.env || true",
]:
    _i, o, e = ssh.exec_command(cmd)
    print(o.read().decode().strip())
ssh.close()
