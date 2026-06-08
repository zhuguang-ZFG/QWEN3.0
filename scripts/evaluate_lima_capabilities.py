#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 系统综合能力评估工具
评估系统性能、稳定性和功能完整性
"""

import paramiko
import sys
import io
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ALIYUN_SERVER = '47.112.162.80'
ALIYUN_PASSWORD = 'zhuguang110!'

def check_system_performance(ssh):
    """检查系统性能"""
    results = {}

    # CPU 负载
    stdin, stdout, stderr = ssh.exec_command('uptime | awk -F"load average:" \'{print $2}\'')
    load = stdout.read().decode().strip()
    results['cpu_load'] = load

    # 内存使用
    stdin, stdout, stderr = ssh.exec_command('free -m | grep Mem | awk \'{print $3"/"$2}\'')
    memory = stdout.read().decode().strip()
    results['memory_usage'] = memory

    # 磁盘使用
    stdin, stdout, stderr = ssh.exec_command('df -h / | tail -1 | awk \'{print $5}\'')
    disk = stdout.read().decode().strip()
    results['disk_usage'] = disk

    return results

def check_lima_capabilities(ssh):
    """检查 LiMa 功能能力"""
    capabilities = {}

    # 检查后端数量
    stdin, stdout, stderr = ssh.exec_command('curl -s http://127.0.0.1:8080/admin/api/backends 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0"')
    backends = stdout.read().decode().strip()
    capabilities['backend_count'] = backends

    # 检查缓存功能
    stdin, stdout, stderr = ssh.exec_command('ls /opt/lima-router/semantic_cache_enhanced.py >/dev/null 2>&1 && echo "YES" || echo "NO"')
    cache = stdout.read().decode().strip()
    capabilities['cache_enabled'] = cache == 'YES'

    # 检查 OpenCode 集成
    stdin, stdout, stderr = ssh.exec_command('ls /opt/lima-router/opencode_*.py 2>/dev/null | wc -l')
    opencode = stdout.read().decode().strip()
    capabilities['opencode_modules'] = opencode

    return capabilities

def run_performance_test(ssh):
    """运行性能测试"""
    test_results = {}

    # 测试 API 响应时间
    stdin, stdout, stderr = ssh.exec_command('''
for i in {1..5}; do
    curl -o /dev/null -s -w "%{time_total}\\n" http://127.0.0.1:8080/health
    sleep 0.5
done | awk '{sum+=$1; count++} END {print sum/count}'
''', timeout=30)
    avg_response = stdout.read().decode().strip()
    test_results['avg_health_check'] = avg_response

    return test_results

def generate_report(system_perf, capabilities, perf_test):
    """生成评估报告"""
    print('='*70)
    print('LiMa 系统综合能力评估报告')
    print('='*70)
    print(f'\n生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    print('\n[1] 系统性能:')
    print(f'  CPU 负载: {system_perf.get("cpu_load", "N/A")}')
    print(f'  内存使用: {system_perf.get("memory_usage", "N/A")}')
    print(f'  磁盘使用: {system_perf.get("disk_usage", "N/A")}')

    print('\n[2] LiMa 功能能力:')
    print(f'  后端数量: {capabilities.get("backend_count", "0")}')
    print(f'  缓存功能: {"启用" if capabilities.get("cache_enabled") else "未启用"}')
    print(f'  OpenCode 模块: {capabilities.get("opencode_modules", "0")} 个')

    print('\n[3] 性能测试:')
    print(f'  平均响应时间: {perf_test.get("avg_health_check", "N/A")}s')

    print('\n[4] 综合评分:')
    score = calculate_score(system_perf, capabilities, perf_test)
    print(f'  系统评分: {score}/100')
    print(f'  等级: {get_grade(score)}')

    print('\n[5] 优化建议:')
    suggestions = get_suggestions(system_perf, capabilities, perf_test, score)
    for i, suggestion in enumerate(suggestions, 1):
        print(f'  {i}. {suggestion}')

def calculate_score(system_perf, capabilities, perf_test):
    """计算综合评分"""
    score = 50  # 基础分

    # 缓存功能 +15
    if capabilities.get('cache_enabled'):
        score += 15

    # OpenCode 模块 +10
    if int(capabilities.get('opencode_modules', 0)) >= 30:
        score += 10

    # 后端数量 +10
    if int(capabilities.get('backend_count', 0)) >= 5:
        score += 10

    # 响应时间 +15
    try:
        response_time = float(perf_test.get('avg_health_check', 1.0))
        if response_time < 0.1:
            score += 15
        elif response_time < 0.5:
            score += 10
    except:
        pass

    return min(score, 100)

def get_grade(score):
    """获取等级"""
    if score >= 90:
        return 'A (优秀)'
    elif score >= 80:
        return 'B (良好)'
    elif score >= 70:
        return 'C (中等)'
    else:
        return 'D (需改进)'

def get_suggestions(system_perf, capabilities, perf_test, score):
    """获取优化建议"""
    suggestions = []

    if score < 80:
        suggestions.append('系统评分较低，建议全面优化')

    if not capabilities.get('cache_enabled'):
        suggestions.append('启用 Redis 缓存以提升性能')

    try:
        disk_usage = int(system_perf.get('disk_usage', '0%').rstrip('%'))
        if disk_usage > 70:
            suggestions.append(f'磁盘使用率 {disk_usage}%，建议清理')
    except:
        pass

    if int(capabilities.get('backend_count', 0)) < 5:
        suggestions.append('后端数量较少，建议增加备用后端')

    try:
        response_time = float(perf_test.get('avg_health_check', 1.0))
        if response_time > 0.5:
            suggestions.append(f'响应时间 {response_time}s 较慢，建议优化')
    except:
        pass

    if not suggestions:
        suggestions.append('系统运行良好，继续保持')

    return suggestions

def main():
    print('='*70)
    print('LiMa 系统综合能力评估')
    print('='*70)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print('\n连接到 VPS...')
        ssh.connect(ALIYUN_SERVER, username='root', password=ALIYUN_PASSWORD, timeout=10)
        print('[OK] 连接成功')

        print('\n[1/3] 检查系统性能...')
        system_perf = check_system_performance(ssh)

        print('[2/3] 检查 LiMa 功能...')
        capabilities = check_lima_capabilities(ssh)

        print('[3/3] 运行性能测试...')
        perf_test = run_performance_test(ssh)

        ssh.close()

        print('\n' + '='*70)
        generate_report(system_perf, capabilities, perf_test)
        print('='*70)

    except Exception as e:
        print(f'\n[错误] 评估失败: {e}')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
