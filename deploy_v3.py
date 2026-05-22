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
PASS = os.environ.get("LIMA_DEPLOY_PASS")
KEY_PATH = os.environ.get("LIMA_DEPLOY_KEY_PATH")
REMOTE_DIR = "/opt/lima-router"

FILES_TO_DEPLOY = [
    "router_v3.py",
    "health_tracker.py",
    "sticky_session.py",
    "v3_integration.py",
    "patch_server_v3.py",
    "server.py",
    "routing_engine.py",
]

# Phase 7-25 module directories to deploy
DIRS_TO_DEPLOY = [
    "context_pipeline",
    "session_memory",
    "user_identity",
]


def _preflight() -> None:
    if not PASS and not KEY_PATH:
        sys.exit("ERROR: set LIMA_DEPLOY_PASS or LIMA_DEPLOY_KEY_PATH")


def main():
    _preflight()
    print("=== LiMa V3 Deploy ===")
    print(f"Target: {SERVER}:{REMOTE_DIR}")

    # 1. Connect
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_args = {"username": USER}
    if KEY_PATH:
        connect_args["key_filename"] = KEY_PATH
    else:
        connect_args["password"] = PASS
    ssh.connect(SERVER, **connect_args)
    sftp = ssh.open_sftp()
    print("[1/5] Connected")

    # 2. Backup current server.py
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = f"{REMOTE_DIR}/server.py.bak.{ts}"
    ssh.exec_command(f"cp {REMOTE_DIR}/server.py {backup}")
    print(f"[2/5] Backup: {backup}")
    print("Rollback:")
    print(f"  cp {backup} {REMOTE_DIR}/server.py")
    print("  systemctl restart lima-router")

    # 3. Upload V3 modules
    for f in FILES_TO_DEPLOY:
        local = os.path.join(os.path.dirname(__file__), f)
        remote = f"{REMOTE_DIR}/{f}"
        sftp.put(local, remote)
        print(f"  Uploaded: {f}")

    # 3.1 Upload Phase 7-25 module directories
    base_dir = os.path.dirname(__file__)
    for d in DIRS_TO_DEPLOY:
        local_dir = os.path.join(base_dir, d)
        if not os.path.isdir(local_dir):
            continue
        remote_dir = f"{REMOTE_DIR}/{d}"
        try:
            sftp.mkdir(remote_dir)
        except IOError:
            pass
        for fname in os.listdir(local_dir):
            if fname.endswith(".py"):
                sftp.put(os.path.join(local_dir, fname), f"{remote_dir}/{fname}")
                print(f"  Uploaded: {d}/{fname}")
    print("[3/5] Files deployed")

    # 3.5 Run patch script on server
    stdin, stdout, stderr = ssh.exec_command(
        f"cd {REMOTE_DIR} && /usr/local/bin/python3.10 patch_server_v3.py"
    )
    patch_out = stdout.read().decode("utf-8", errors="replace")
    print(f"  Patch output:\n{patch_out}")

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
