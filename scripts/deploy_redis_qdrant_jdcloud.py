#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
京东云 Redis + Qdrant 一键部署脚本

执行流程:
Phase 1: Redis 缓存层
  1.1 上传安装脚本
  1.2 执行安装
  1.3 配置安全参数
  1.4 配置防火墙
  1.5 测试连接

Phase 2: Qdrant 向量检索
  2.1 上传安装脚本
  2.2 执行安装
  2.3 配置防火墙
  2.4 测试连接
"""

import paramiko
import sys
import time
import io
from pathlib import Path

# 修复 Windows 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 服务器配置
JDCLOUD_SERVER = "117.72.118.95"
JDCLOUD_PASSWORD = "XINdandan521!"

# 需要上传的脚本
SCRIPTS = [
    ("deploy/jdcloud/install_redis.sh", "/tmp/install_redis.sh"),
    ("deploy/jdcloud/configure_redis.sh", "/tmp/configure_redis.sh"),
    ("deploy/jdcloud/configure_firewall.sh", "/tmp/configure_firewall.sh"),
]


def main():
    print("="*60)
    print("京东云增强部署 - Redis + Qdrant")
    print("="*60)

    # 默认部署 Phase 1 (Redis)
    import sys
    phase = sys.argv[1] if len(sys.argv) > 1 else "1"

    print(f"\n部署阶段: {phase}")

    if phase in ["0", "1"]:
        deploy_phase1_redis()

    if phase in ["0", "2"]:
        print("\n[提示] Phase 2 Qdrant 部署将在 Phase 1 成功后进行")

    print("\n" + "="*60)
    print("[完成] 部署流程结束")
    print("="*60)


def deploy_phase1_redis():
    """部署 Phase 1: Redis 缓存层"""
    print("\n" + "="*60)
    print("Phase 1: Redis 缓存层部署")
    print("="*60)

    # 连接京东云
    print("\n[1/5] 连接京东云服务器...")
    ssh = connect_jdcloud()

    # 上传脚本
    print("\n[2/5] 上传安装脚本...")
    upload_scripts(ssh)

    # 执行安装
    print("\n[3/5] 执行 Redis 安装...")
    execute_script(ssh, "/tmp/install_redis.sh", "安装 Redis")

    # 执行配置
    print("\n[4/5] 配置 Redis（生成密码）...")
    print("\n" + "!"*60)
    print("重要：正在生成 Redis 密码...")
    print("!"*60)

    output = execute_script(ssh, "/tmp/configure_redis.sh", "配置 Redis", timeout=300)

    # 提取密码
    redis_password = extract_redis_password(output)
    if redis_password:
        print("\n" + "="*60)
        print("Redis 密码已生成（请保存）:")
        print("="*60)
        print(f"\n  {redis_password}\n")
        print("="*60)

        # 保存到本地
        password_file = Path.home() / "Downloads" / "redis_password.txt"
        with open(password_file, "w") as f:
            f.write(f"REDIS_PASSWORD={redis_password}\n")
        print(f"\n已保存到: {password_file}")

    # 配置防火墙
    print("\n[5/5] 配置防火墙...")
    execute_script(ssh, "/tmp/configure_firewall.sh", "配置防火墙")

    ssh.close()

    print("\n" + "="*60)
    print("[Phase 1 完成] Redis 缓存层部署成功")
    print("="*60)
    print("\n下一步: 在阿里云 VPS 测试连接")
    print("  1. SSH 登录阿里云 VPS: ssh root@47.112.162.80")
    print(f"  2. 设置密码: export REDIS_PASSWORD='{redis_password}'")
    print("  3. 测试连接: bash scripts/test_redis_connection.sh")
    print("\n或者运行:")
    print(f"  python scripts/test_redis_from_aliyun.py")


def connect_jdcloud():
    """连接到京东云服务器"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            JDCLOUD_SERVER,
            username='root',
            password=JDCLOUD_PASSWORD,
            timeout=10
        )
        print(f"[OK] 已连接到 {JDCLOUD_SERVER}")
        return ssh
    except Exception as e:
        print(f"[ERROR] 连接失败: {e}")
        sys.exit(1)


def upload_scripts(ssh):
    """上传脚本到京东云"""
    sftp = ssh.open_sftp()

    for local_file, remote_file in SCRIPTS:
        if not Path(local_file).exists():
            print(f"[WARN] 文件不存在: {local_file}")
            continue

        try:
            sftp.put(local_file, remote_file)
            ssh.exec_command(f"chmod +x {remote_file}")
            print(f"[OK] 已上传 {local_file}")
        except Exception as e:
            print(f"[ERROR] 上传 {local_file} 失败: {e}")

    sftp.close()


def execute_script(ssh, script_path, description, timeout=120):
    """执行远程脚本"""
    print(f"\n--- 执行: {description} ---")

    stdin, stdout, stderr = ssh.exec_command(f"bash {script_path}", timeout=timeout)

    # 实时输出
    output_lines = []
    for line in stdout:
        line = line.strip()
        print(f"  {line}")
        output_lines.append(line)

    # 检查错误
    errors = stderr.read().decode()
    if errors:
        print(f"\n[WARN] 警告/错误:\n{errors}")

    exit_code = stdout.channel.recv_exit_status()
    if exit_code != 0:
        print(f"\n[ERROR] 脚本执行失败 (exit code: {exit_code})")
        sys.exit(1)

    print(f"[OK] {description} 完成")
    return "\n".join(output_lines)


def extract_redis_password(output):
    """从输出中提取 Redis 密码"""
    for line in output.split("\n"):
        if "REDIS_PASSWORD=" in line:
            parts = line.split("=")
            if len(parts) == 2:
                return parts[1].strip()
    return None


if __name__ == "__main__":
    main()
