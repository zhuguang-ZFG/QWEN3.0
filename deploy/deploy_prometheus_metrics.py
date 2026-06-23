#!/usr/bin/env python3
"""部署 Prometheus 业务指标支持到阿里云 VPS"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import deploy_config

try:
    import paramiko
except ImportError:
    print("错误: 需要安装 paramiko")
    print("运行: pip install paramiko")
    sys.exit(1)

VPS_HOST = deploy_config.LIMA_SERVER
VPS_USER = "root"
VPS_KEY_FILE = deploy_config.expanded_key_path()
VPS_DIR = deploy_config.REMOTE_PATH
LIMA_SERVICE = "lima-router"

FILES_TO_DEPLOY = [
    "routes/request_tracking.py",
    "observability/prometheus_exporter.py",
    "server_lifespan.py",
]


def deploy_file(sftp, local_path, remote_path):
    """上传单个文件"""
    try:
        sftp.put(local_path, remote_path)
        return True
    except Exception as e:
        print(f"Upload failed: {e}")
        return False


def _connect_ssh() -> paramiko.SSHClient | int:
    """Establish an SSH connection to the VPS and return the client or an error code."""
    print(f"Connecting to {VPS_HOST}...")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    known_hosts = deploy_config.expanded_known_hosts()
    if os.path.exists(known_hosts):
        try:
            ssh.load_host_keys(known_hosts)
        except Exception as e:
            print(f"[WARN] Failed to load {known_hosts}: {e}")
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

    try:
        if os.path.exists(VPS_KEY_FILE):
            ssh.connect(VPS_HOST, username=VPS_USER, key_filename=VPS_KEY_FILE, timeout=10)
        else:
            print(f"Key file not found: {VPS_KEY_FILE}")
            print("Please configure SSH key")
            return 1
    except Exception as e:
        print(f"SSH connection failed: {e}")
        return 1

    print("SSH connected successfully")
    print()
    return ssh


def _deploy_files(sftp) -> int:
    """Upload all files in FILES_TO_DEPLOY. Returns 0 on success, 1 on failure."""
    print("Files to deploy:")
    for file in FILES_TO_DEPLOY:
        print(f"  - {file}")
    print()

    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    for file in FILES_TO_DEPLOY:
        print(f"Deploying {file}...")
        local_path = file
        remote_path = f"{VPS_DIR}/{file}"

        if not os.path.exists(local_path):
            print(f"Local file not found: {local_path}")
            continue

        if deploy_file(sftp, local_path, remote_path):
            print(f"OK: {file} deployed")
        else:
            print(f"FAIL: {file} deployment failed")
            return 1

    return 0


def _configure_env(ssh: paramiko.SSHClient) -> None:
    """Ensure LIMA_PROMETHEUS_METRICS=1 is present in the remote .env."""
    print("=== Configure .env ===")
    stdin, stdout, stderr = ssh.exec_command(
        f'cd {VPS_DIR} && grep -q "^LIMA_PROMETHEUS_METRICS=" .env 2>/dev/null && '
        'echo "EXISTS" || (echo "LIMA_PROMETHEUS_METRICS=1" >> .env && echo "ADDED")'
    )
    result = stdout.read().decode().strip()
    if result == "EXISTS":
        print("OK: LIMA_PROMETHEUS_METRICS already in .env")
    elif result == "ADDED":
        print("OK: Added LIMA_PROMETHEUS_METRICS=1 to .env")
    else:
        print(f"Config result: {result}")


def _restart_service(ssh: paramiko.SSHClient) -> None:
    """Restart the LiMa systemd service and print a status summary."""
    print()
    print("=== Restart LiMa Service ===")
    stdin, stdout, stderr = ssh.exec_command(
        f"systemctl restart {LIMA_SERVICE} && sleep 3 && systemctl status {LIMA_SERVICE} --no-pager"
    )
    output = stdout.read().decode()
    error = stderr.read().decode()

    if "active (running)" in output:
        print("OK: LiMa service restarted")
        print(output[:400])
    else:
        print("WARNING: LiMa service status:")
        print(output[:400])
        if error:
            print("Error:", error[:200])


def main() -> int:
    print("=== Deploy Prometheus Metrics to Aliyun VPS ===")
    print()

    ssh_or_code = _connect_ssh()
    if isinstance(ssh_or_code, int):
        return ssh_or_code
    ssh = ssh_or_code

    sftp = ssh.open_sftp()
    try:
        if _deploy_files(sftp) != 0:
            return 1
    finally:
        sftp.close()

    _configure_env(ssh)
    _restart_service(ssh)

    ssh.close()

    print()
    print("=== Deployment Complete ===")
    print("Prometheus endpoint: https://chat.donglicao.com/v1/ops/metrics/prometheus")
    print("Please wait 30-60 seconds for JDCloud Prometheus to scrape new metrics...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
