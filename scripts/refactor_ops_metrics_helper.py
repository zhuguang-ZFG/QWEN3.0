#!/usr/bin/env python3
"""ops_metrics 重构辅助脚本

帮助自动化提取和迁移函数到子模块。
使用方式: python scripts/refactor_ops_metrics_helper.py
"""
import re
from pathlib import Path


def extract_function_blocks(source_file: Path) -> dict[str, str]:
    """从源文件提取所有函数定义及其完整代码块"""
    content = source_file.read_text(encoding='utf-8')
    functions = {}

    # 匹配函数定义 (def function_name...)
    pattern = r'^(def _\w+.*?)(?=\ndef |\nclass |\n@router|\Z)'
    matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)

    for match in matches:
        func_block = match.group(1).rstrip()
        # 提取函数名
        func_name_match = re.match(r'def (_\w+)', func_block)
        if func_name_match:
            func_name = func_name_match.group(1)
            functions[func_name] = func_block

    return functions


def classify_functions(functions: dict[str, str]) -> dict[str, list[str]]:
    """将函数分类到各个子模块"""
    classification = {
        'formatters': [],  # 已完成
        'collectors': [],
        'correlator': [],
        'main': []
    }

    # 已在 formatters.py 中的函数
    formatters_done = {
        '_redacted', '_backend_call_count', '_backend_call_detail',
        '_top_backend_counts', '_top_backend_details'
    }

    # 关联追踪相关
    correlator_keywords = ['correlat', 'sanitize', 'trace']

    for func_name in functions:
        if func_name in formatters_done:
            classification['formatters'].append(func_name)
        elif any(kw in func_name.lower() for kw in correlator_keywords):
            classification['correlator'].append(func_name)
        elif func_name.startswith('_get_') or func_name.endswith('_stats') or func_name.endswith('_metrics') or func_name.endswith('_snapshot'):
            classification['collectors'].append(func_name)
        elif func_name == '_app_stats' or 'recent' in func_name:
            classification['collectors'].append(func_name)
        else:
            classification['main'].append(func_name)

    return classification


def generate_report():
    """生成重构进度报告"""
    source = Path('routes/ops_metrics.py')
    if not source.exists():
        print(f"❌ 源文件不存在: {source}")
        return

    functions = extract_function_blocks(source)
    classification = classify_functions(functions)

    print("=" * 60)
    print("ops_metrics.py 重构分析报告")
    print("=" * 60)
    print(f"\n总函数数: {len(functions)}")

    for module, func_list in classification.items():
        print(f"\n【{module}】 ({len(func_list)} 个函数)")
        for func in func_list:
            loc = len(functions[func].split('\n'))
            print(f"  - {func} ({loc} 行)")

    print("\n" + "=" * 60)
    print("下一步操作:")
    print("=" * 60)
    print("1. collectors.py: 需迁移", len(classification['collectors']), "个函数")
    print("2. correlator.py: 需迁移", len(classification['correlator']), "个函数")
    print("3. 主文件重构: 保留", len(classification['main']), "个函数 + 3 个端点")
    print("\n建议按照 routes/ops_metrics/REFACTOR_MANUAL.md 手动执行")


if __name__ == '__main__':
    generate_report()
