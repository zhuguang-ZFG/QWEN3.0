"""Generate test skeletons from coverage analysis."""

from __future__ import annotations

import os
from pathlib import Path

from scripts.coverage.analyzer import PROJECT, analyze


def generate_tests(module_filter: str) -> str:
    """为指定模块的未覆盖函数生成测试骨架"""
    results = analyze(module_filter)

    if module_filter not in results:
        return f"模块 '{module_filter}' 未找到"

    mod = results[module_filter]

    lines = []
    lines.append(f'"""Tests for {module_filter}."""')
    lines.append("")
    lines.append("import pytest")
    lines.append("")

    # 引用现有测试的模式
    test_dir = PROJECT / "tests"
    ref_tests = list(test_dir.glob(f"test_{module_filter}*.py"))
    if ref_tests:
        lines.append("# 参考现有测试模式:")
        for rt in ref_tests[:3]:
            lines.append(f"#   {rt.name}")
    lines.append("")

    for i, fn in enumerate(mod.get("uncovered_list", [])[:10]):
        fn_file = fn["file"].replace(".py", "").replace(os.sep, ".")
        import_path = ".".join(Path(fn_file).parts)

        lines.append(f"from {import_path} import {fn['name']}")

    lines.append("")

    for fn in mod.get("uncovered_list", [])[:10]:
        test_name = f"test_{fn['name']}"
        if test_name.startswith("test_test_"):
            test_name = test_name.replace("test_test_", "test_", 1)

        lines.append("")
        lines.append("@pytest.mark.skip(reason='auto-generated skeleton; replace with behavioral test')")
        lines.append(f"def {test_name}():")
        lines.append(f'    """TODO: behavioral test for {fn["name"]}."""')
        lines.append("    pytest.skip('replace generated skeleton with real test')")

    return "\n".join(lines)
