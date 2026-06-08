#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
京东云 Hermes Gateway 一键部署脚本

部署流程:
1. 上传必要文件到京东云
2. 执行环境安装脚本
3. 启动服务
4. 验证健康检查
"""

import paramiko
import sys
import time
from pathlib import Path

# 服务器配置
SERVER = "117.72.118.95"
PASSWORD = "XINdandan521!"
REMOTE_DIR = "/opt/hermes-gateway"

# 需要上传的文件
LOCAL_FILES = [
    "hermes_api.py",
    "hermes_bridge.py",
    "hermes_gateway.py",
]

def main():
    print("="*60)
    print("京东云 Hermes Gateway 一键部署")
    print("="*60)

    # 1. 连接服务器
    print("\n[1/6] 连接京东云服务器...")
    ssh = connect_server()

    # 2. 上传安装脚本
    print("\n[2/6] 上传安装脚本...")
    upload_install_script(ssh)

    # 3. 执行环境安装
    print("\n[3/6] 执行环境安装...")
    execute_install(ssh)

    # 4. 上传应用文件
    print("\n[4/6] 上传应用文件...")
    upload_app_files(ssh)

    # 5. 配置并启动服务
    print("\n[5/6] 配置并启动服务...")
    start_service(ssh)

    # 6. 验证部署
    print("\n[6/6] 验证部署...")
    verify_deployment(ssh)

    ssh.close()

    print("\n" + "="*60)
    print("✓ 部署完成!")
    print("="*60)
    print("\n下一步:")
    print("1. 在阿里云 VPS 上注册 hermes-agent 后端")
    print("2. 测试端到端调用")
    print("3. 监控日志: ssh root@117.72.118.95 'journalctl -u hermes-gateway -f'")
    print("\n部署文档: docs/superpowers/plans/2026-06-08-jdcloud-deployment-plan.md")

def connect_server():
    """连接到京东云服务器"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(SERVER, username='root', password=PASSWORD, timeout=10)
        print(f"✓ 已连接到 {SERVER}")
        return ssh
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        sys.exit(1)

def upload_install_script(ssh):
    """上传安装脚本"""
    sftp = ssh.open_sftp()

    local_script = "deploy/jdcloud/install_hermes.sh"
    remote_script = "/tmp/install_hermes.sh"

    try:
        sftp.put(local_script, remote_script)
        ssh.exec_command(f"chmod +x {remote_script}")
        print(f"✓ 已上传安装脚本")
    except Exception as e:
        print(f"✗ 上传失败: {e}")
        sys.exit(1)
    finally:
        sftp.close()

def execute_install(ssh):
    """执行环境安装"""
    stdin, stdout, stderr = ssh.exec_command("/tmp/install_hermes.sh", timeout=300)

    print("\n--- 安装输出 ---")
    for line in stdout:
        print(line.strip())

    errors = stderr.read().decode()
    if errors:
        print("\n--- 警告/错误 ---")
        print(errors)

    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"\n✗ 安装失败 (exit code: {exit_code})")
        sys.exit(1)

    print("\n✓ 环境安装完成")

def upload_app_files(ssh):
    """上传应用文件"""
    sftp = ssh.open_sftp()

    for local_file in LOCAL_FILES:
        remote_file = f"{REMOTE_DIR}/{local_file}"

        if not Path(local_file).exists():
            print(f"✗ 文件不存在: {local_file}")
            continue

        try:
            sftp.put(local_file, remote_file)
            print(f"✓ 已上传 {local_file}")
        except Exception as e:
            print(f"✗ 上传 {local_file} 失败: {e}")

    sftp.close()

def start_service(ssh):
    """配置并启动服务"""
    # 提示用户配置 API Key
    print("\n请确认已配置 LIMA_API_KEY:")
    print(f"  ssh root@{SERVER}")
    print(f"  nano {REMOTE_DIR}/.env")
    print("\n按回车继续...")
    input()

    # 启动服务
    commands = [
        "systemctl daemon-reload",
        "systemctl enable hermes-gateway",
        "systemctl start hermes-gateway",
    ]

    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()  # 等待命令完成

    time.sleep(2)  # 等待服务启动

    # 检查服务状态
    stdin, stdout, stderr = ssh.exec_command("systemctl status hermes-gateway --no-pager")
    output = stdout.read().decode()

    if "active (running)" in output:
        print("✓ 服务已启动")
    else:
        print("✗ 服务启动失败")
        print(output)
        sys.exit(1)

def verify_deployment(ssh):
    """验证部署"""
    # 检查健康端点
    stdin, stdout, stderr = ssh.exec_command(
        "curl -s http://127.0.0.1:8699/health"
    )
    output = stdout.read().decode()

    if "ok" in output:
        print("✓ 健康检查通过")
        print(f"   响应: {output}")
    else:
        print("✗ 健康检查失败")
        print(f"   响应: {output}")

if __name__ == "__main__":
    main()
