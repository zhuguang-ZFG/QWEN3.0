#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查京东云服务器配置"""
import paramiko
import sys
import io

# 修复 Windows 控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SERVER = "117.72.118.95"
PASSWORD = "XINdandan521!"

def check_config():
    """通过 SSH 查询服务器配置"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"正在连接 {SERVER}...")
        ssh.connect(SERVER, username='root', password=PASSWORD, timeout=10)
        print("[OK] SSH 连接成功\n")

        commands = {
            "CPU 核心数": "nproc",
            "CPU 型号": "cat /proc/cpuinfo | grep 'model name' | head -1 | awk -F: '{print $2}' | xargs",
            "内存信息": "free -h | grep Mem",
            "硬盘空间": "df -h / | tail -1",
            "系统版本": "cat /etc/os-release | grep PRETTY_NAME | cut -d'\"' -f2",
            "内核版本": "uname -r",
        }

        results = {}
        for name, cmd in commands.items():
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if output:
                results[name] = output
                print(f"[INFO] {name}: {output}")
            elif error:
                print(f"[WARN] {name}: 查询失败 - {error}")

        ssh.close()

        # 解析并输出配置档位
        print("\n" + "="*60)
        analyze_config(results)

    except paramiko.AuthenticationException:
        print("[ERROR] 认证失败：密码错误")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"[ERROR] SSH 错误：{e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 连接失败：{e}")
        sys.exit(1)

def analyze_config(results):
    """分析配置档位并给出建议"""
    print("\n[配置档位分析]")
    print("="*60)

    # 解析 CPU 核心数
    cpu_cores = int(results.get("CPU 核心数", "0"))

    # 解析内存（从 "Mem: 7.6Gi 234Mi 6.8Gi ..." 格式提取）
    mem_line = results.get("内存信息", "")
    mem_total_str = mem_line.split()[1] if len(mem_line.split()) > 1 else "0"
    mem_total_gb = 0
    if "Gi" in mem_total_str:
        mem_total_gb = float(mem_total_str.replace("Gi", ""))
    elif "Mi" in mem_total_str:
        mem_total_gb = float(mem_total_str.replace("Mi", "")) / 1024

    # 解析硬盘
    disk_line = results.get("硬盘空间", "")
    disk_total_str = disk_line.split()[1] if len(disk_line.split()) > 1 else "0"

    print(f"CPU:  {cpu_cores} 核")
    print(f"内存: {mem_total_gb:.1f} GB")
    print(f"硬盘: {disk_total_str}")
    print()

    # 判断档位
    if cpu_cores <= 2 and mem_total_gb <= 4:
        tier = "入门型"
        print(f"\n[配置档位] {tier} (1-2核, 2-4GB)")
        print("\n[可行方案]")
        print("  * Hermes Agent Gateway (推荐)")
        print("  * 向量检索 Qdrant (小型代码库)")
        print("\n[不可行方案]")
        print("  * 本地模型推理 (内存不足)")
        print("  * LiMa Router 完整副本 (性能不足)")

    elif cpu_cores <= 4 and mem_total_gb <= 8:
        tier = "标准型"
        print(f"\n[配置档位] {tier} (2-4核, 4-8GB)")
        print("\n[可行方案]")
        print("  * Hermes Gateway + Qdrant 组合 (推荐)")
        print("  * 本地推理 7B 模型 (可尝试)")
        print("  * LiMa Router 副本")
        print("\n[性能有限]")
        print("  * 32B 大模型 (内存不足)")

    else:
        tier = "进阶型"
        print(f"\n[配置档位] {tier} (4+核, 8+GB)")
        print("\n[所有方案都可行]")
        print("  * 本地推理 Ollama (强烈推荐) *****")
        print("    - Qwen2.5-Coder:7B (流畅)")
        print("    - DeepSeek-R1:14B (推理模型)")
        if mem_total_gb >= 16:
            print("    - Qwen2.5-Coder:32B (大模型)")
        print("  * Hermes Gateway")
        print("  * 向量检索 Qdrant")
        print("  * LiMa Router 副本")

    print("\n" + "="*60)
    print("\n[详细部署方案]")
    print("   docs/superpowers/plans/2026-06-08-jdcloud-resource-analysis.md")

if __name__ == "__main__":
    check_config()
