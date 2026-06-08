#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存健康检查工具
快速检查 Redis 缓存系统健康状态
"""

import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'
REDIS_HOST = '100.85.114.65'
REDIS_PASSWORD = 'reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q='

def health_check():
    """执行健康检查"""
    print('='*70)
    print('Redis 缓存健康检查')
    print('='*70)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)

        checks = []

        # 1. Redis 连接
        print('\n[1/5] 检查 Redis 连接...')
        stdin, stdout, stderr = ssh.exec_command(f'redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" ping 2>&1 | tail -1')
        result = stdout.read().decode().strip()
        redis_ok = 'PONG' in result
        checks.append(('Redis 连接', redis_ok))
        print(f'  {"✓" if redis_ok else "✗"} Redis 连接')

        # 2. LiMa 服务
        print('\n[2/5] 检查 LiMa 服务...')
        stdin, stdout, stderr = ssh.exec_command('systemctl is-active lima-router')
        lima_status = stdout.read().decode().strip()
        lima_ok = lima_status == 'active'
        checks.append(('LiMa 服务', lima_ok))
        print(f'  {"✓" if lima_ok else "✗"} LiMa 服务: {lima_status}')

        # 3. 缓存模块
        print('\n[3/5] 检查缓存模块...')
        test_cmd = '''
cd /opt/lima-router
python3.10 << 'PYTEST'
import sys
import os
os.environ["REDIS_HOST"] = "100.85.114.65"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_PASSWORD"] = "reu/0E4Y3k+5yyaFqFbL6V1uw6wfs0UXfZk145xpp/Q="
try:
    import semantic_cache_enhanced as cache
    status = cache.get_connection_status()
    print("OK" if status.get("available") else "FAIL")
except Exception as e:
    print("ERROR")
PYTEST
'''
        stdin, stdout, stderr = ssh.exec_command(test_cmd, timeout=30)
        module_result = stdout.read().decode().strip()
        module_ok = module_result == 'OK'
        checks.append(('缓存模块', module_ok))
        print(f'  {"✓" if module_ok else "✗"} 缓存模块')

        # 4. 缓存键
        print('\n[4/5] 检查缓存数据...')
        stdin, stdout, stderr = ssh.exec_command(f'redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" DBSIZE 2>&1 | tail -1')
        dbsize = stdout.read().decode().strip()
        has_data = dbsize.isdigit() and int(dbsize) > 0
        checks.append(('缓存数据', has_data))
        print(f'  {"✓" if has_data else "ℹ"} 缓存键: {dbsize}')

        # 5. 命中统计
        print('\n[5/5] 检查命中率...')
        stdin, stdout, stderr = ssh.exec_command(f'redis-cli -h {REDIS_HOST} -p 6379 -a "{REDIS_PASSWORD}" INFO stats 2>&1 | grep keyspace_hits')
        hits_line = stdout.read().decode().strip()
        if 'keyspace_hits:' in hits_line:
            hits = int(hits_line.split(':')[1])
            has_hits = hits > 0
            checks.append(('缓存命中', has_hits))
            print(f'  {"✓" if has_hits else "ℹ"} 缓存命中: {hits}')
        else:
            checks.append(('缓存命中', False))
            print(f'  ℹ 缓存命中: 0')

        # 总结
        print('\n' + '='*70)
        print('健康检查结果')
        print('='*70)

        passed = sum(1 for _, ok in checks if ok)
        total = len(checks)

        for name, ok in checks:
            status = '✓ 正常' if ok else '✗ 异常' if name in ['Redis 连接', 'LiMa 服务', '缓存模块'] else 'ℹ 等待数据'
            print(f'  {status:10s} {name}')

        print(f'\n通过: {passed}/{total}')

        if passed >= 3:
            print('\n✅ 系统健康')
        elif passed >= 2:
            print('\n⚠️  系统部分正常')
        else:
            print('\n❌ 系统异常')

        ssh.close()
        return passed >= 3

    except Exception as e:
        print(f'\n❌ 健康检查失败: {e}')
        return False

if __name__ == '__main__':
    success = health_check()
    sys.exit(0 if success else 1)
