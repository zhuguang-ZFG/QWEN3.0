#!/usr/bin/env python3
import paramiko
import os

KEY = os.path.expanduser("~/.ssh/id_ed25519")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.112.162.80", username="root", key_filename=KEY, timeout=60)
cmds = [
    "ls -la /opt/lima-router/scripts/ 2>&1 | head -10",
    "python3.10 -m pip show hermes-agent 2>&1 | head -5",
    "python3.10 -c 'import gateway.platforms.weixin; print(\"ok\")' 2>&1",
]
for c in cmds:
    _i, o, e = ssh.exec_command(c)
    print(c, "->", (o.read() + e.read()).decode()[:300])
ssh.close()
