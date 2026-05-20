#!/usr/bin/env python3
"""
deploy_v3.py — 一键部署 V3 路由到服务器
遵循 Superpowers 原则: 本地验证通过后一次性替换

用法: python deploy_v3.py
"""

import paramiko
import sys
import time
import os

SERVER = "47.112.162.80"
USER = "root"
PASS = "zhuguang110!"
REMOTE_DIR = "/opt/lima-router"

FILES_TO_DEPLOY = [
    "router_v3.py",
    "health_tracker.py",
    "sticky_session.py",
    "v3_integration.py",
]


def main():
    print("=== LiMa V3 Deploy ===")
    print(f"Target: {SERVER}:{REMOTE_DIR}")

    # 1. Connect
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, password=PASS)
    sftp = ssh.open_sftp()
    print("[1/5] Connected")

    # 2. Backup current server.py
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = f"{REMOTE_DIR}/server.py.bak.{ts}"
    ssh.exec_command(f"cp {REMOTE_DIR}/server.py {backup}")
    print(f"[2/5] Backup: {backup}")

    # 3. Upload V3 modules
    for f in FILES_TO_DEPLOY:
        local = os.path.join(os.path.dirname(__file__), f)
        remote = f"{REMOTE_DIR}/{f}"
        sftp.put(local, remote)
        print(f"  Uploaded: {f}")
    print("[3/5] Files deployed")

    # 4. Restart server
    ssh.exec_command('pkill -9 -f "python3.10 server.py"')
    time.sleep(3)
    ssh.exec_command('fuser -k 8080/tcp 2>/dev/null')
    time.sleep(2)
    cmd = f"cd {REMOTE_DIR} && nohup /usr/local/bin/python3.10 server.py > /var/log/lima-server.log 2>&1 &"
    ssh.exec_command(cmd)
    time.sleep(5)
    print("[4/5] Server restarted")

    # 5. Verify
    stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 8080")
    port = stdout.read().decode().strip()
    if port:
        print("[5/5] Server UP on 8080")
    else:
        stdin, stdout, stderr = ssh.exec_command("tail -5 /var/log/lima-server.log")
        log = stdout.read().decode("utf-8", errors="replace")
        print(f"[5/5] FAILED! Log:\n{log}")
        print(f"\nRollback: cp {backup} {REMOTE_DIR}/server.py && restart")
        sftp.close()
        ssh.close()
        sys.exit(1)

    sftp.close()
    ssh.close()
    print("\nDeploy complete!")


if __name__ == "__main__":
    main()
