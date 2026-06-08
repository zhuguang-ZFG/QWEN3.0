#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 性能监控增强工具
实时监控系统性能和健康状态
"""

import paramiko
import sys
import io
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

def monitor_performance():
    """监控性能指标"""
    print('='*70)
    print('LiMa 性能监控')
    print('='*70)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)

        metrics = {}

        # 1. API 响应时间
        print('\n[1/5] 测试 API 响应时间...')
        stdin, stdout, stderr = ssh.exec_command('''
for i in {1..5}; do
    curl -o /dev/null -s -w "%{time_total}\\n" http://127.0.0.1:8080/health
    sleep 0.5
done | awk '{sum+=$1; count++} END {print sum/count}'
''', timeout=30)
        avg_response = stdout.read().decode().strip()
        metrics['avg_response_time'] = float(avg_response) if avg_response else 0
        print(f'  平均响应时间: {avg_response}s')

        # 2. 系统负载
        print('\n[2/5] 检查系统负载...')
        stdin, stdout, stderr = ssh.exec_command('uptime | awk -F"load average:" \'{print $2}\'')
        load = stdout.read().decode().strip()
        metrics['system_load'] = load
        print(f'  系统负载: {load}')

        # 3. 内存使用
        print('\n[3/5] 检查内存使用...')
        stdin, stdout, stderr = ssh.exec_command('free -m | grep Mem | awk \'{print int($3/$2*100)}\'')
        mem = stdout.read().decode().strip()
        metrics['memory_usage'] = int(mem) if mem else 0
        print(f'  内存使用: {mem}%')

        # 4. 缓存状态
        print('\n[4/5] 检查缓存状态...')
        stdin, stdout, stderr = ssh.exec_command('redis-cli -h 100.85.114.65 -p 6379 -a "reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q=" INFO stats 2>&1 | grep keyspace_hits')
        cache_stats = stdout.read().decode()
        if 'keyspace_hits' in cache_stats:
            print('[OK] 缓存正常')
            metrics['cache_status'] = 'OK'
        else:
            print('[INFO] 缓存状态未知')
            metrics['cache_status'] = 'Unknown'

        # 5. 服务状态
        print('\n[5/5] 检查服务状态...')
        stdin, stdout, stderr = ssh.exec_command('systemctl is-active lima-router')
        service = stdout.read().decode().strip()
        metrics['service_status'] = service
        print(f'  Lima-router: {service}')

        ssh.close()

        # 生成报告
        print('\n' + '='*70)
        print('性能监控报告')
        print('='*70)
        print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'响应时间: {metrics.get("avg_response_time", 0):.3f}s')
        print(f'系统负载: {metrics.get("system_load", "N/A")}')
        print(f'内存使用: {metrics.get("memory_usage", 0)}%')
        print(f'缓存状态: {metrics.get("cache_status", "Unknown")}')
        print(f'服务状态: {metrics.get("service_status", "Unknown")}')

        # 评估
        if metrics.get('avg_response_time', 1) < 0.1 and \
           metrics.get('memory_usage', 100) < 90 and \
           metrics.get('service_status') == 'active':
            print('\n[优秀] 系统运行状态良好')
        else:
            print('\n[提示] 系统可能需要优化')

    except Exception as e:
        print(f'\n[错误] 监控失败: {e}')

def main():
    """执行性能监控"""
    import argparse

    parser = argparse.ArgumentParser(description='LiMa 性能监控工具')
    parser.add_argument('--continuous', action='store_true', help='持续监控模式')
    parser.add_argument('--interval', type=int, default=60, help='监控间隔(秒)')

    args = parser.parse_args()

    if args.continuous:
        print('持续监控模式 (按 Ctrl+C 停止)\n')
        try:
            while True:
                monitor_performance()
                print(f'\n等待 {args.interval} 秒...\n')
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print('\n\n监控已停止')
    else:
        monitor_performance()

if __name__ == '__main__':
    main()
