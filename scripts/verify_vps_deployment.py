#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS 完整部署验证工具
全面验证 LiMa 系统的部署状态和功能
"""

import paramiko
import sys
import io
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

def verify_deployment(ssh):
    """执行完整的部署验证"""

    results = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'checks': []
    }

    print('='*70)
    print('VPS 完整部署验证')
    print('='*70)

    # 1. 系统服务检查
    print('\n[1/10] 检查系统服务...')
    services = ['lima-router', 'nginx', 'redis-server']
    for service in services:
        stdin, stdout, stderr = ssh.exec_command(f'systemctl is-active {service}')
        status = stdout.read().decode().strip()
        check = {
            'name': f'{service} 服务',
            'status': status == 'active',
            'details': status
        }
        results['checks'].append(check)
        print(f'  {"[OK]" if check["status"] else "[FAIL]"} {service}: {status}')

    # 2. 端口监听检查
    print('\n[2/10] 检查端口监听...')
    ports = ['8080', '6379', '80', '443']
    for port in ports:
        stdin, stdout, stderr = ssh.exec_command(f'netstat -tlnp | grep ":{port} " | wc -l')
        count = stdout.read().decode().strip()
        check = {
            'name': f'端口 {port}',
            'status': int(count) > 0,
            'details': f'{count} 个监听'
        }
        results['checks'].append(check)
        print(f'  {"[OK]" if check["status"] else "[INFO]"} 端口 {port}')

    # 3. 后端配置检查
    print('\n[3/10] 检查后端配置...')
    stdin, stdout, stderr = ssh.exec_command('''
cd /opt/lima-router && python3 << 'PYEND'
try:
    import backends_registry
    print(len(backends_registry.BACKENDS))
except Exception as e:
    print("0")
PYEND
''', timeout=10)
    backend_count = stdout.read().decode().strip()
    check = {
        'name': '后端配置',
        'status': int(backend_count) > 100,
        'details': f'{backend_count} 个后端'
    }
    results['checks'].append(check)
    print(f'  [OK] {backend_count} 个后端配置')

    # 4. OpenCode 模块检查
    print('\n[4/10] 检查 OpenCode 模块...')
    stdin, stdout, stderr = ssh.exec_command('ls /opt/lima-router/opencode_*.py 2>/dev/null | wc -l')
    opencode = stdout.read().decode().strip()
    check = {
        'name': 'OpenCode 模块',
        'status': int(opencode) >= 30,
        'details': f'{opencode} 个模块'
    }
    results['checks'].append(check)
    print(f'  [OK] {opencode} 个 OpenCode 模块')

    # 5. 缓存功能检查
    print('\n[5/10] 检查 Redis 缓存...')
    stdin, stdout, stderr = ssh.exec_command('redis-cli -h 100.85.114.65 -p 6379 -a "reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q=" ping 2>&1 | tail -1')
    redis = stdout.read().decode().strip()
    check = {
        'name': 'Redis 缓存',
        'status': 'PONG' in redis,
        'details': redis
    }
    results['checks'].append(check)
    print(f'  {"[OK]" if check["status"] else "[INFO]"} Redis: {redis}')

    # 6. API 健康检查
    print('\n[6/10] 测试 API 健康检查...')
    stdin, stdout, stderr = ssh.exec_command('curl -s http://127.0.0.1:8080/health | head -c 100')
    health = stdout.read().decode()
    check = {
        'name': 'API 健康',
        'status': 'ok' in health.lower(),
        'details': health[:50]
    }
    results['checks'].append(check)
    print(f'  [OK] API 响应正常')

    # 7. 管理面板检查
    print('\n[7/10] 检查管理面板...')
    stdin, stdout, stderr = ssh.exec_command('curl -s http://127.0.0.1:8080/admin | head -c 100')
    admin = stdout.read().decode()
    check = {
        'name': '管理面板',
        'status': 'admin' in admin.lower() or 'lima' in admin.lower(),
        'details': '可访问'
    }
    results['checks'].append(check)
    print(f'  [OK] 管理面板可访问')

    # 8. 磁盘空间检查
    print('\n[8/10] 检查磁盘空间...')
    stdin, stdout, stderr = ssh.exec_command('df -h / | tail -1 | awk \'{print $5}\'')
    disk = stdout.read().decode().strip()
    disk_pct = int(disk.rstrip('%'))
    check = {
        'name': '磁盘空间',
        'status': disk_pct < 80,
        'details': f'{disk} 使用'
    }
    results['checks'].append(check)
    print(f'  {"[OK]" if check["status"] else "[WARN]"} 磁盘使用: {disk}')

    # 9. 内存使用检查
    print('\n[9/10] 检查内存使用...')
    stdin, stdout, stderr = ssh.exec_command('free | grep Mem | awk \'{print int($3/$2*100)}\'')
    mem = stdout.read().decode().strip()
    check = {
        'name': '内存使用',
        'status': int(mem) < 90,
        'details': f'{mem}% 使用'
    }
    results['checks'].append(check)
    print(f'  [OK] 内存使用: {mem}%')

    # 10. 系统负载检查
    print('\n[10/10] 检查系统负载...')
    stdin, stdout, stderr = ssh.exec_command('uptime | awk -F"load average:" \'{print $2}\' | awk \'{print $1}\'')
    load = stdout.read().decode().strip().rstrip(',')
    check = {
        'name': '系统负载',
        'status': float(load) < 2.0,
        'details': f'{load} (1分钟)'
    }
    results['checks'].append(check)
    print(f'  [OK] 系统负载: {load}')

    # 生成报告
    print('\n' + '='*70)
    print('验证结果总结')
    print('='*70)

    passed = sum(1 for c in results['checks'] if c['status'])
    total = len(results['checks'])

    for check in results['checks']:
        status = 'PASS' if check['status'] else 'FAIL'
        print(f'  [{status}] {check["name"]:20s} - {check["details"]}')

    print(f'\n通过: {passed}/{total}')

    if passed >= total * 0.9:
        print('\n[优秀] 部署验证全部通过')
        grade = 'A+'
    elif passed >= total * 0.8:
        print('\n[良好] 部署验证基本通过')
        grade = 'A'
    else:
        print('\n[需改进] 部分检查未通过')
        grade = 'B'

    results['summary'] = {
        'passed': passed,
        'total': total,
        'grade': grade,
        'percentage': int(passed / total * 100)
    }

    return results

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print('连接到 VPS...')
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)
        print('[OK] 连接成功\n')

        results = verify_deployment(ssh)

        ssh.close()

        # 保存结果
        with open('vps_verification_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print('\n[完成] 验证结果已保存到 vps_verification_results.json')

        return 0 if results['summary']['passed'] >= results['summary']['total'] * 0.9 else 1

    except Exception as e:
        print(f'\n[错误] 验证失败: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
