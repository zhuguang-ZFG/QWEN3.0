#!/usr/bin/env python3
"""
LiMa 测试覆盖分析器（轻量版，直接分析文件 AST）。
从源代码提取函数 → 比对测试文件 → 找出未覆盖代码。

用法:
  python scripts/analyze_test_coverage.py --summary      # 模块覆盖概览
  python scripts/analyze_test_coverage.py -m routing_selector  # 指定模块
  python scripts/analyze_test_coverage.py -m routing_selector -g  # 生成测试
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.coverage.analyzer import CORE_MODULES, PROJECT, analyze
from scripts.coverage.skeleton import generate_tests


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", "-s", action="store_true", help="模块覆盖概览")
    parser.add_argument("-m", "--module", help="分析指定模块")
    parser.add_argument("-g", "--generate", action="store_true", help="(和 -m 一起用) 生成测试骨架")
    args = parser.parse_args()

    if args.summary:
        results = analyze(None)
        print("=== LiMa 测试覆盖概览 ===")
        print(f"{'模块':28s} {'描述':10s} {'函数':>5s} {'名匹配%':>7s} {'测试文件':>6s} {'测试函数':>6s}")
        print("-" * 78)
        for mod, info in sorted(results.items(), key=lambda x: x[1]["total"], reverse=True):
            name_rate = info["rate"]
            test_files = info["test_file_count"]
            test_funcs = info["name_matched_tests"]
            if test_files == 0 and test_funcs == 0:
                status = " [无导入测试]"
            elif name_rate < 10 and test_files >= 3:
                status = " [有测试,名匹配低]"
            elif name_rate < 50:
                status = " [低名匹配]"
            else:
                status = ""
            print(
                f"{mod:28s} {info['description']:10s} {info['total']:5d} "
                f"{name_rate:6.1f}% {test_files:6d} {test_funcs:6d}{status}"
            )
        print()
        print("说明: 「名匹配%」仅按测试函数名≈源码函数名估算，易误报 0 测试。")
        print("      「测试文件」= tests/ 内 import 该模块 的文件数（更可信）。")
        return

    if args.module:
        if args.generate:
            skel = generate_tests(args.module)
            out = PROJECT / "tests" / f"test_{args.module}_generated.py"
            out.write_text(skel, encoding="utf-8")
            print(f"✅ 测试骨架已写入 {out}")
            print(skel[:500])
        else:
            results = analyze(args.module)
            if args.module in results:
                mod = results[args.module]
                print(f"\n=== {args.module}: {mod['total']} 个函数, 名匹配 {mod['rate']}% ===")
                print(f"导入测试文件: {mod['test_file_count']}  名匹配测试函数: {mod['name_matched_tests']}")
                if mod["test_files"]:
                    print("测试文件:")
                    for tf in mod["test_files"][:12]:
                        print(f"  - {tf}")
                    if len(mod["test_files"]) > 12:
                        print(f"  ... +{len(mod['test_files']) - 12} more")
                print(f"已覆盖(名匹配): {mod['covered']}  未覆盖: {mod['uncovered']}")
                for fn in mod.get("uncovered_list", [])[:15]:
                    print(f"  - {fn['name']:30s} ({fn['file']})")
            return


if __name__ == "__main__":
    main()
