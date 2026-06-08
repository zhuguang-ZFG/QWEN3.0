#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
官网和 Chat 平台监控工具
定期检查网站状态和性能
"""

import paramiko
import sys
import io
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

SITES = {
    'Chat 平台': 'https://chat.donglicao.com',
    '官网': 'https://donglicao.com',
    'API': 'https://api.donglicao.com/health',
}

def check_site(ssh, name, url):
    """检查单个站点"""
    cmd = f'curl -o /dev/null -s -w "%{{http_code}}|%{{time_total}}" {url}'
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    result = stdout.read().decode().strip()

    try:
        status, time_total = result.split('|')
        status = int(status)
        time_total = float(time_total)

        return {
            'name': name,
            'url': url,
            'status': status,
            'time': time_total,
            'ok': status == 200 and time_total < 2.0
        }
    except:
        return {
            'name': name,
            'url': url,
            'status': 0,
            'time': 0,
            'ok': False
        }

def monitor():
    """执行监控"""
    print('='*70)
    print(f'官网和 Chat 平台监控 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*70)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)

        results = []

        for name, url in SITES.items():
            print(f'\n检查 {name}...')
            result = check_site(ssh, name, url)
            results.append(result)

            status_icon = 'OK' if result['ok'] else 'WARN'
            print(f'  [{status_icon}] 状态: {result["status"]} | 时间: {result["time"]:.2f}s')

        ssh.close()

        # 总结
        print('\n' + '='*70)
        print('监控总结')
        print('='*70)

        all_ok = all(r['ok'] for r in results)

        for r in results:
            status = 'OK' if r['ok'] else 'FAIL'
            print(f'  [{status}] {r["name"]:10s} {r["status"]} | {r["time"]:.2f}s')

        if all_ok:
            print('\n[OK] 所有站点运行正常')
        else:
            print('\n[WARN] 部分站点需要检查')

        return all_ok

    except Exception as e:
        print(f'\n[错误] 监控失败: {e}')
        return False

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='官网和 Chat 平台监控')
    parser.add_argument('--once', action='store_true', help='单次检查')
    parser.add_argument('--interval', type=int, default=300, help='检查间隔(秒)')

    args = parser.parse_args()

    if args.once:
        monitor()
    else:
        print(f'持续监控模式 (间隔 {args.interval} 秒)')
        print('按 Ctrl+C 停止\n')

        try:
            while True:
                monitor()
                print(f'\n等待 {args.interval} 秒...\n')
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print('\n\n监控已停止')
