#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiMa 代码分析工具
分析代码质量、识别优化点和死区代码
"""

import os
import sys
import ast
import re
from collections import defaultdict
from pathlib import Path

def analyze_imports(file_path):
    """分析文件的导入"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.append(name.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return imports
    except Exception as e:
        return []

def find_functions(file_path):
    """查找文件中的函数定义"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)

        return functions
    except Exception as e:
        return []

def find_classes(file_path):
    """查找文件中的类定义"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())

        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)

        return classes
    except Exception as e:
        return []

def find_todos(file_path):
    """查找 TODO/FIXME 标记"""
    todos = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if re.search(r'TODO|FIXME|HACK|XXX|DEPRECATED', line, re.IGNORECASE):
                    todos.append((i, line.strip()))
    except Exception:
        pass
    return todos

def analyze_file_size(file_path):
    """分析文件大小"""
    try:
        return os.path.getsize(file_path)
    except Exception:
        return 0

def main():
    print('='*70)
    print('LiMa 代码分析工具')
    print('='*70)

    project_root = Path('.')

    # 收集所有 Python 文件
    py_files = []
    for root, dirs, files in os.walk(project_root):
        # 跳过虚拟环境和测试
        dirs[:] = [d for d in dirs if d not in ['.venv', '.venv310', '.git', '__pycache__', 'tests']]

        for file in files:
            if file.endswith('.py'):
                py_files.append(Path(root) / file)

    print(f'\n找到 {len(py_files)} 个 Python 文件')

    # 分析导入
    print('\n[1/5] 分析导入...')
    import_count = defaultdict(int)
    for f in py_files:
        imports = analyze_imports(f)
        for imp in imports:
            import_count[imp] += 1

    print('  最常用的导入 (Top 10):')
    for imp, count in sorted(import_count.items(), key=lambda x: -x[1])[:10]:
        print(f'    {imp:30s} {count:3d} 次')

    # 分析文件大小
    print('\n[2/5] 分析文件大小...')
    large_files = []
    for f in py_files:
        size = analyze_file_size(f)
        if size > 10000:  # > 10KB
            large_files.append((f, size))

    large_files.sort(key=lambda x: -x[1])
    print('  大文件 (> 10KB, Top 10):')
    for f, size in large_files[:10]:
        print(f'    {str(f):50s} {size//1024:4d} KB')

    # 查找 TODO
    print('\n[3/5] 查找 TODO/FIXME...')
    total_todos = 0
    files_with_todos = []
    for f in py_files:
        todos = find_todos(f)
        if todos:
            total_todos += len(todos)
            files_with_todos.append((f, len(todos)))

    print(f'  共发现 {total_todos} 个 TODO/FIXME 标记')
    files_with_todos.sort(key=lambda x: -x[1])
    print('  文件分布 (Top 10):')
    for f, count in files_with_todos[:10]:
        print(f'    {str(f):50s} {count:3d} 个')

    # 分析模块
    print('\n[4/5] 分析模块结构...')
    modules = defaultdict(int)
    for f in py_files:
        parts = f.parts
        if len(parts) > 1 and parts[0] == '.':
            module = parts[1] if len(parts) > 2 else 'root'
            modules[module] += 1

    print('  模块分布 (Top 15):')
    for mod, count in sorted(modules.items(), key=lambda x: -x[1])[:15]:
        print(f'    {mod:30s} {count:3d} 文件')

    # 生成优化建议
    print('\n[5/5] 生成优化建议...')
    print('\n  优化建议:')

    if len(large_files) > 0:
        print(f'  - 发现 {len(large_files)} 个大文件 (> 10KB), 建议拆分')

    if total_todos > 0:
        print(f'  - 发现 {total_todos} 个 TODO/FIXME, 建议清理')

    if len(py_files) > 500:
        print(f'  - 文件数量 ({len(py_files)}) 较多, 建议精简')

    print('\n' + '='*70)
    print('分析完成')
    print('='*70)

    # 生成报告
    report_path = Path('docs/code_analysis_report.txt')
    report_path.parent.mkdir(exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('LiMa 代码分析报告\n')
        f.write('='*70 + '\n\n')
        f.write(f'总文件数: {len(py_files)}\n')
        f.write(f'TODO/FIXME: {total_todos}\n')
        f.write(f'大文件数: {len(large_files)}\n')

    print(f'\n报告已保存到: {report_path}')

if __name__ == '__main__':
    main()
