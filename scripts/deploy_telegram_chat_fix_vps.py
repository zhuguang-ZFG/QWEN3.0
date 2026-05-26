#!/usr/bin/env python3
"""Deploy Telegram /chat fallback fix."""
import os, time, paramiko
from pathlib import Path

KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
REMOTE = "/opt/lima-router"
FILES = [
    "identity_guard.py",
    "routes/telegram_chat_identity.py",
    "routes/telegram_chat_stream.py",
    "routes/telegram_commands.py",
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)
base = Path(__file__).resolve().parents[1]
for rel in FILES:
    sftp = ssh.open_sftp()
    sftp.put(str(base / rel), f"{REMOTE}/{rel.replace(chr(92), '/')}")
    sftp.close()
    print(f"uploaded {rel}")
ssh.exec_command("systemctl restart lima-router")
time.sleep(8)
_i, o, _e = ssh.exec_command("systemctl is-active lima-router")
print("service", o.read().decode().strip())
ssh.close()
