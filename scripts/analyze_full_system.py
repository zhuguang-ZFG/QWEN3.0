#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 系统全面分析工具
生成详细的优化报告和任务清单
"""

import os
import sys
import ast
import re
from pathlib import Path
from collections import defaultdict
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def analyze_file(file_path):
    """分析单个文件"""
    result = {
        'size': 0,
        'lines': 0,
        'functions': 0,
        'classes': 0,
        'todos': 0,
        'imports': 0,
    }

    try:
        result['size'] = os.path.getsize(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            result['lines'] = len(content.split('\n'))
            result['todos'] = len(re.findall(r'TODO|FIXME|HACK|XXX', content))

            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        result['functions'] += 1
                    elif isinstance(node, ast.ClassDef):
                        result['classes'] += 1
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        result['imports'] += 1
            except:
                pass

    except Exception as e:
        pass

    return result

def main():
    print('='*70)
    print('LiMa 系统全面分析')
    print('='*70)

    project_root = Path('.')

    # 收集所有文件
    py_files = []
    md_files = []

    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in ['.venv', '.venv310', '.git', '__pycache__']]

        for file in files:
            file_path = Path(root) / file
            if file.endswith('.py'):
                py_files.append(file_path)
            elif file.endswith('.md'):
                md_files.append(file_path)

    print(f'\n找到 {len(py_files)} 个 Python 文件')
    print(f'找到 {len(md_files)} 个文档文件')

    # 分析关键文件
    print('\n[1/5] 分析关键文件...')
    key_files = {
        'routes/admin_ui.py': '管理面板',
        'server.py': '主服务器',
        'routing_engine.py': '路由引擎',
        'backends.py': '后端管理',
    }

    issues = []

    for file, desc in key_files.items():
        if os.path.exists(file):
            stats = analyze_file(file)
            size_kb = stats['size'] // 1024
            print(f'  {desc:15s} {file:30s} {size_kb:4d}KB {stats["lines"]:4d}行')

            if size_kb > 50:
                issues.append(f'大文件: {file} ({size_kb}KB) - 建议拆分')
            if stats['todos'] > 0:
                issues.append(f'TODO: {file} 有 {stats["todos"]} 个待办')

    # 分析模块
    print('\n[2/5] 分析模块结构...')
    modules = defaultdict(lambda: {'files': 0, 'size': 0, 'lines': 0, 'todos': 0})

    for f in py_files:
        parts = f.parts
        if len(parts) > 1:
            module = parts[1] if parts[0] == '.' else parts[0]
            if module not in ['tests', 'scripts']:
                stats = analyze_file(f)
                modules[module]['files'] += 1
                modules[module]['size'] += stats['size']
                modules[module]['lines'] += stats['lines']
                modules[module]['todos'] += stats['todos']

    print('  核心模块 (Top 10):')
    for mod, stats in sorted(modules.items(), key=lambda x: -x[1]['files'])[:10]:
        size_kb = stats['size'] // 1024
        print(f'    {mod:25s} {stats["files"]:3d}文件 {size_kb:5d}KB {stats["todos"]:2d}TODO')

    # 分析文档
    print('\n[3/5] 分析文档...')
    doc_issues = []
    for f in md_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
                if re.search(r'2024|2025|废弃|过时|TODO', content):
                    doc_issues.append(str(f))
        except:
            pass

    print(f'  可能过时的文档: {len(doc_issues)} 个')

    # 统计 TODO
    print('\n[4/5] 统计 TODO/FIXME...')
    total_todos = sum(m['todos'] for m in modules.values())
    print(f'  总计: {total_todos} 个')

    # 生成报告
    print('\n[5/5] 生成优化报告...')

    report = f"""LiMa 系统全面分析报告
{'='*70}

基本信息:
  Python 文件: {len(py_files)}
  文档文件: {len(md_files)}
  核心模块: {len(modules)}
  TODO/FIXME: {total_todos}

关键问题:
"""

    for issue in issues[:10]:
        report += f'  - {issue}\n'

    if doc_issues:
        report += f'\n文档问题:\n'
        for doc in doc_issues[:10]:
            report += f'  - {doc}\n'

    report += f"""
优化建议:
  高优先级:
    1. 拆分 admin_ui.py ({key_files.get('routes/admin_ui.py', 'N/A')})
    2. 清理 {total_todos} 个 TODO/FIXME
    3. 更新 {len(doc_issues)} 个过时文档

  中优先级:
    4. 优化模块结构
    5. 统一代码风格
    6. 改进性能
"""

    # 保存报告
    report_path = Path('docs/full_system_analysis_report.txt')
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f'\n报告已保存: {report_path}')
    print('\n' + '='*70)
    print('分析完成')
    print('='*70)

if __name__ == '__main__':
    main()
