#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
后端管理面板问题诊断和修复工具
"""

import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

def diagnose_admin_panel():
    """诊断管理面板问题"""
    print('='*70)
    print('后端管理面板问题诊断')
    print('='*70)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    issues_found = []

    try:
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)

        # 1. 检查认证问题
        print('\n[1/6] 检查认证状态...')
        stdin, stdout, stderr = ssh.exec_command('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/admin')
        code = stdout.read().decode().strip()
        if code == '401':
            issues_found.append('认证失败 - 需要登录')
            print('[ISSUE] HTTP 401 - 需要认证')
        elif code == '200':
            print('[OK] 认证通过')
        else:
            print(f'[INFO] HTTP {code}')

        # 2. 检查 JavaScript 加载
        print('\n[2/6] 检查 JavaScript 代码...')
        stdin, stdout, stderr = ssh.exec_command('curl -s http://127.0.0.1:8080/admin | grep -o "function.*(" | head -5')
        js_funcs = stdout.read().decode()
        if js_funcs:
            print('[OK] JavaScript 函数存在')
        else:
            issues_found.append('JavaScript 代码可能缺失或损坏')
            print('[ISSUE] JavaScript 函数未找到')

        # 3. 检查 API 路由
        print('\n[3/6] 检查 API 路由...')
        api_endpoints = [
            '/admin/api/backends',
            '/admin/api/stats',
            '/admin/api/model-status'
        ]

        for endpoint in api_endpoints:
            stdin, stdout, stderr = ssh.exec_command(f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8080{endpoint}')
            code = stdout.read().decode().strip()
            if code in ['200', '401']:
                print(f'  [OK] {endpoint} - HTTP {code}')
            else:
                issues_found.append(f'{endpoint} 返回 HTTP {code}')
                print(f'  [ISSUE] {endpoint} - HTTP {code}')

        # 4. 检查 CORS 配置
        print('\n[4/6] 检查 CORS 配置...')
        stdin, stdout, stderr = ssh.exec_command('grep -r "CORSMiddleware" /opt/lima-router/*.py | head -1')
        cors = stdout.read().decode()
        if cors:
            print('[OK] CORS 已配置')
        else:
            print('[INFO] CORS 配置未找到')

        # 5. 检查服务状态
        print('\n[5/6] 检查服务状态...')
        stdin, stdout, stderr = ssh.exec_command('systemctl is-active lima-router')
        status = stdout.read().decode().strip()
        if status == 'active':
            print('[OK] Lima-router 运行正常')
        else:
            issues_found.append(f'服务状态异常: {status}')
            print(f'[ISSUE] 服务状态: {status}')

        # 6. 检查最近错误
        print('\n[6/6] 检查应用错误日志...')
        stdin, stdout, stderr = ssh.exec_command('journalctl -u lima-router --since "5 minutes ago" --no-pager | grep -i "error\\|exception\\|traceback" | tail -5')
        errors = stdout.read().decode()
        if errors:
            issues_found.append('发现应用错误日志')
            print('[WARN] 发现错误:')
            print(errors[:500])
        else:
            print('[OK] 无明显错误')

        ssh.close()

        # 生成诊断报告
        print('\n' + '='*70)
        print('诊断报告')
        print('='*70)

        if issues_found:
            print(f'\n发现 {len(issues_found)} 个问题:')
            for i, issue in enumerate(issues_found, 1):
                print(f'  {i}. {issue}')
        else:
            print('\n[OK] 未发现明显问题')

        # 提供解决方案
        print('\n' + '='*70)
        print('解决方案')
        print('='*70)

        if '认证失败' in str(issues_found):
            print('\n问题 1: 认证失败 (HTTP 401)')
            print('原因: 管理面板需要登录认证')
            print('解决方案:')
            print('  1. 访问 https://chat.donglicao.com/admin')
            print('  2. 使用管理员密码登录')
            print('  3. 或部署免密登录功能 (admin_passwordless_login.py)')

        if 'JavaScript' in str(issues_found):
            print('\n问题 2: JavaScript 功能异常')
            print('解决方案:')
            print('  1. 检查浏览器控制台错误')
            print('  2. 清除浏览器缓存')
            print('  3. 检查 admin_ui.py 文件完整性')

        if not issues_found:
            print('\n可能的原因:')
            print('  1. 需要登录认证才能使用功能')
            print('  2. 浏览器 JavaScript 被禁用')
            print('  3. 网络或 CORS 问题')
            print('\n建议:')
            print('  1. 打开浏览器开发者工具 (F12)')
            print('  2. 查看 Console 标签的错误信息')
            print('  3. 查看 Network 标签的请求状态')

    except Exception as e:
        print(f'\n[错误] 诊断失败: {e}')

def main():
    print('='*70)
    print('LiMa 后端管理面板诊断工具')
    print('='*70)

    diagnose_admin_panel()

    print('\n' + '='*70)
    print('[完成] 诊断完成')
    print('='*70)

if __name__ == '__main__':
    main()
