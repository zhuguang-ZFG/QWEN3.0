#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 后端管理优化工具
检查和优化后端配置
"""

import paramiko
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

def check_backends(ssh):
    """检查当前后端配置"""
    print('='*70)
    print('检查 LiMa 后端配置')
    print('='*70)

    # 1. 通过 API 获取后端信息
    print('\n[1/3] 获取后端列表...')
    cmd = '''
curl -s http://127.0.0.1:8080/admin/api/backends 2>/dev/null || echo "[]"
'''
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
    backends_json = stdout.read().decode()

    try:
        backends = json.loads(backends_json)
        print(f'[OK] 找到 {len(backends)} 个后端')

        if backends:
            print('\n后端列表:')
            for i, backend in enumerate(backends[:10], 1):
                name = backend.get('name', backend.get('id', 'Unknown'))
                status = backend.get('status', 'unknown')
                print(f'  {i}. {name:30s} {status}')
    except:
        print('[INFO] 无法解析后端配置')
        backends = []

    # 2. 检查后端配置文件
    print('\n[2/3] 检查配置文件...')
    stdin, stdout, stderr = ssh.exec_command('ls -la /opt/lima-router/backends*.py 2>/dev/null')
    files = stdout.read().decode()
    if files:
        print('[OK] 找到后端配置文件')
    else:
        print('[INFO] 未找到后端配置文件')

    # 3. 建议
    print('\n[3/3] 优化建议:')
    if len(backends) < 3:
        print('  [建议] 当前仅 {} 个后端，建议增加到至少 3 个'.format(len(backends)))
        print('  [方案] 配置多个 API 提供商作为备用')
    else:
        print('  [OK] 后端数量充足')

    print('\n' + '='*70)
    print('[完成] 后端检查完成')
    print('='*70)

    return backends

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)
        backends = check_backends(ssh)
        ssh.close()

        return 0 if backends else 1

    except Exception as e:
        print(f'\n[错误] 检查失败: {e}')
        return 1

if __name__ == '__main__':
    sys.exit(main())
