#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 代码质量检查工具
检查 Bug、逻辑错误和潜在问题
"""

import os
import re
import ast
import sys
from pathlib import Path

def check_code_quality():
    """执行代码质量检查"""
    print('='*70)
    print('LiMa 代码质量检查')
    print('='*70)

    issues = {
        'critical': [],
        'warnings': [],
        'suggestions': []
    }

    # 1. 检查常见 Bug 模式
    print('\n[1/5] 检查常见 Bug 模式...')

    patterns = {
        'bare_except': r'except\s*:',
        'hardcoded_secrets': r'(password|secret|api_key)\s*=\s*["\'][^"\']+["\']',
        'sql_injection': r'execute\([^?].*%.*\)',
        'print_statements': r'^\s*print\(',
        'todo_fixme': r'(TODO|FIXME|XXX|HACK)',
    }

    python_files = list(Path('.').rglob('*.py'))
    print(f'扫描 {len(python_files)} 个 Python 文件...')

    for file_path in python_files[:100]:  # 限制前 100 个文件
        if '.venv' in str(file_path) or 'node_modules' in str(file_path):
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # 检查 bare except
                if re.search(patterns['bare_except'], content):
                    issues['warnings'].append(f'{file_path}: Bare except clause found')

                # 检查硬编码密钥
                if re.search(patterns['hardcoded_secrets'], content, re.IGNORECASE):
                    secrets = re.findall(patterns['hardcoded_secrets'], content, re.IGNORECASE)
                    if secrets and 'test' not in str(file_path).lower():
                        issues['critical'].append(f'{file_path}: Possible hardcoded secret')

                # 检查 TODO/FIXME
                todos = re.findall(patterns['todo_fixme'], content)
                if len(todos) > 3:
                    issues['suggestions'].append(f'{file_path}: {len(todos)} TODO/FIXME comments')

        except Exception as e:
            pass

    # 2. 检查语法错误
    print('\n[2/5] 检查 Python 语法...')
    syntax_errors = 0
    for file_path in python_files[:50]:
        if '.venv' in str(file_path):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            issues['critical'].append(f'{file_path}: Syntax error at line {e.lineno}')
            syntax_errors += 1

    print(f'语法检查完成: {syntax_errors} 个错误')

    # 3. 检查导入问题
    print('\n[3/5] 检查导入问题...')
    for file_path in python_files[:50]:
        if '.venv' in str(file_path):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 检查循环导入风险
                if content.count('from') > 20:
                    issues['suggestions'].append(f'{file_path}: Many imports, check for circular dependencies')
        except:
            pass

    # 4. 检查配置文件
    print('\n[4/5] 检查配置文件...')
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            env_content = f.read()
            if 'password' in env_content.lower() or 'secret' in env_content.lower():
                issues['warnings'].append('.env: Contains sensitive data (ensure .gitignore)')

    # 5. 检查后端配置
    print('\n[5/5] 检查后端配置完整性...')
    if os.path.exists('backends_registry'):
        backend_files = list(Path('backends_registry').rglob('*.py'))
        print(f'后端配置文件: {len(backend_files)} 个')

    # 生成报告
    print('\n' + '='*70)
    print('代码质量报告')
    print('='*70)

    print(f'\n🔴 关键问题: {len(issues["critical"])} 个')
    for issue in issues['critical'][:5]:
        print(f'  • {issue}')

    print(f'\n⚠️  警告: {len(issues["warnings"])} 个')
    for issue in issues['warnings'][:5]:
        print(f'  • {issue}')

    print(f'\n💡 建议: {len(issues["suggestions"])} 个')
    for issue in issues['suggestions'][:5]:
        print(f'  • {issue}')

    # 评分
    total_issues = len(issues['critical']) + len(issues['warnings']) + len(issues['suggestions'])
    if len(issues['critical']) == 0:
        score = max(90 - len(issues['warnings']) * 2 - len(issues['suggestions']), 70)
        print(f'\n[优秀] 代码质量评分: {score}/100')
    else:
        score = max(80 - len(issues['critical']) * 5, 50)
        print(f'\n[需改进] 代码质量评分: {score}/100')

    print('\n主要建议:')
    print('  1. 避免使用 bare except')
    print('  2. 使用环境变量存储密钥')
    print('  3. 添加类型注解提升代码质量')
    print('  4. 完善错误处理')

def main():
    print('='*70)
    print('LiMa 代码质量检查工具')
    print('='*70)

    check_code_quality()

    print('\n' + '='*70)
    print('[完成] 代码质量检查完成')
    print('='*70)

if __name__ == '__main__':
    main()
