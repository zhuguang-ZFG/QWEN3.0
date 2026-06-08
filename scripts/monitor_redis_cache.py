#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis 缓存监控脚本
实时监控缓存命中率、性能指标和系统状态
"""

import paramiko
import sys
import io
import time
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'
REDIS_HOST = '100.85.114.65'
REDIS_PASSWORD = 'reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q='

def get_redis_stats(ssh):
    """获取 Redis 统计信息"""
    cmd = f'''
redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" INFO stats 2>&1 | grep -v Warning | grep -E "keyspace_hits|keyspace_misses|total_commands|instantaneous_ops"
'''
    stdin, stdout, stderr = ssh.exec_command(cmd)
    output = stdout.read().decode()

    stats = {}
    for line in output.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            stats[key.strip()] = value.strip()

    return stats

def get_cache_keys_count(ssh):
    """获取缓存键数量"""
    cmd = f'''
redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" KEYS "lima:cache:*" 2>&1 | grep -v Warning | wc -l
'''
    stdin, stdout, stderr = ssh.exec_command(cmd)
    count = stdout.read().decode().strip()
    return int(count) if count.isdigit() else 0

def get_redis_memory(ssh):
    """获取 Redis 内存使用"""
    cmd = f'''
redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" INFO memory 2>&1 | grep -v Warning | grep -E "used_memory_human|used_memory_peak_human|maxmemory_human"
'''
    stdin, stdout, stderr = ssh.exec_command(cmd)
    output = stdout.read().decode()

    memory = {}
    for line in output.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            memory[key.strip()] = value.strip()

    return memory

def calculate_hit_rate(stats):
    """计算缓存命中率"""
    hits = int(stats.get('keyspace_hits', 0))
    misses = int(stats.get('keyspace_misses', 0))
    total = hits + misses

    if total == 0:
        return 0.0

    return (hits / total) * 100

def monitor_once():
    """单次监控"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)

        # 获取统计信息
        stats = get_redis_stats(ssh)
        keys_count = get_cache_keys_count(ssh)
        memory = get_redis_memory(ssh)

        # 计算命中率
        hit_rate = calculate_hit_rate(stats)

        # 显示信息
        print(f'\n{"="*70}')
        print(f'Redis 缓存监控 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'{"="*70}')

        print(f'\n📊 缓存统计:')
        print(f'  缓存键数量: {keys_count}')
        print(f'  命中次数: {stats.get("keyspace_hits", 0)}')
        print(f'  未命中次数: {stats.get("keyspace_misses", 0)}')
        print(f'  命中率: {hit_rate:.2f}%')
        print(f'  总命令数: {stats.get("total_commands_processed", 0)}')

        print(f'\n💾 内存使用:')
        print(f'  当前内存: {memory.get("used_memory_human", "N/A")}')
        print(f'  峰值内存: {memory.get("used_memory_peak_human", "N/A")}')
        print(f'  内存限制: {memory.get("maxmemory_human", "N/A")}')

        # 评估状态
        print(f'\n✅ 状态评估:')
        if keys_count == 0:
            print(f'  ⚠️  缓存为空，等待请求写入')
        elif hit_rate == 0 and int(stats.get("keyspace_misses", 0)) > 0:
            print(f'  ⏳ 缓存已写入，等待命中')
        elif hit_rate > 0:
            if hit_rate >= 30:
                print(f'  ✅ 命中率优秀 ({hit_rate:.1f}%)')
            elif hit_rate >= 20:
                print(f'  ✅ 命中率良好 ({hit_rate:.1f}%)')
            elif hit_rate >= 10:
                print(f'  ⚠️  命中率偏低 ({hit_rate:.1f}%)')
            else:
                print(f'  ⚠️  命中率很低 ({hit_rate:.1f}%)')

        ssh.close()
        return True

    except Exception as e:
        print(f'\n[ERROR] 监控失败: {e}')
        return False

def monitor_continuous(interval=60, duration=3600):
    """持续监控"""
    print(f'\n{"="*70}')
    print(f'开始持续监控')
    print(f'{"="*70}')
    print(f'监控间隔: {interval} 秒')
    print(f'监控时长: {duration} 秒 ({duration//60} 分钟)')
    print(f'\n按 Ctrl+C 停止监控')

    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                print(f'\n监控时长已到 ({duration}秒)，结束监控')
                break

            success = monitor_once()

            if not success:
                print(f'\n等待 {interval} 秒后重试...')

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f'\n\n用户中断，停止监控')

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Redis 缓存监控')
    parser.add_argument('--once', action='store_true', help='单次监控')
    parser.add_argument('--interval', type=int, default=60, help='监控间隔（秒）')
    parser.add_argument('--duration', type=int, default=3600, help='监控时长（秒）')

    args = parser.parse_args()

    if args.once:
        monitor_once()
    else:
        monitor_continuous(args.interval, args.duration)

if __name__ == '__main__':
    main()
