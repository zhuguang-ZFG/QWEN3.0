#!/usr/bin/env python3
"""
LiMa 特性生成规划器。
输入: 特性描述
输出:
  1. 依赖分析（新建/修改哪些文件，生成顺序）
  2. 参考模式（类似功能的现有文件）
  3. 数据流图

使用: python scripts/lima_feature_planner.py "添加 OTA 分段升级端点"
"""

import ast
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from lima_feature_planner_patterns import PATTERNS

PROJECT = Path("D:/QWEN3.0")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def _keyword_rules(desc_lower: str, result: dict) -> None:
    """Apply keyword heuristics to populate touches/references/patterns."""
    # OTA/firmware
    if any(k in desc_lower for k in ("ota", "固件", "升级", "firmware", "release", "版本")):
        result["touches"].append("device_ota")
        result["required_files"].append(
            {
                "path": "routes/{resource}.py",
                "template": "device_route",
                "reason": "设备端 OTA API 端点",
            }
        )
        result["references"].extend(["routes/device_ota.py", "device_ota/release.py", "tests/test_device_ota.py"])
        result["patterns"].append("device_route")

    # routes/API
    if any(k in desc_lower for k in ("路由", "端点", "api", "endpoint", "接口", "interface")):
        result["touches"].append("routes")
        result["patterns"].append("route")
        if not result["required_files"]:
            result["references"].append("routes/device_ota.py")

    # device gateway
    if any(k in desc_lower for k in ("设备", "device", "gateway", "连接", "session")):
        result["touches"].append("device_gateway")
        result["references"].extend(["device_gateway/sessions.py", "device_gateway/task_service.py"])

    # AI backends
    if any(k in desc_lower for k in ("后端", "backend", "provider", "模型", "model", "ai")):
        result["touches"].extend(["routing_selector", "provider_inventory", "backends_registry"])
        result["references"].extend(["routing_selector/filters.py", "routing_selector/helpers.py"])

    # tests
    if any(k in desc_lower for k in ("测试", "test", "集成", "集成测试")):
        result["patterns"].append("test_pattern")

    # services
    if any(k in desc_lower for k in ("服务", "service", "管理", "manager", "handler")):
        result["patterns"].append("service_class")
        result["references"].append("device_gateway/task_service.py")


def _dedupe_lists(result: dict) -> None:
    result["references"] = list(dict.fromkeys(result["references"]))
    result["patterns"] = list(dict.fromkeys(result["patterns"]))
    result["touches"] = list(dict.fromkeys(result["touches"]))


def _resolve_required_file_paths(feature_desc: str, required_files: list) -> None:
    for rf in required_files:
        path = rf["path"]
        if "{resource}" in path:
            resource = feature_desc.lower().replace(" ", "_")[:20]
            rf["path"] = path.replace("{resource}", resource)


def analyze_feature(feature_desc: str) -> dict:
    """分析特性描述，提取关键词、判断文件类型、定位参考"""
    result = {
        "feature": feature_desc,
        "touches": [],
        "required_files": [],
        "modify_files": [],
        "order": [],
        "references": [],
        "patterns": [],
    }

    _keyword_rules(feature_desc.lower(), result)
    _dedupe_lists(result)
    _resolve_required_file_paths(feature_desc, result["required_files"])
    result["order"] = _compute_order(result["required_files"], result["touches"])

    return result


def _compute_order(required_files: list, touches: list) -> list:
    """计算文件创建/修改顺序（按依赖关系）"""
    order = []

    # 1. 数据模型/服务层
    if "device_gateway" in touches or "device_ota" in touches:
        for rf in required_files:
            if "service" in rf.get("template", "") or "class" in rf.get("template", ""):
                order.append({**rf, "step": 1, "action": "create"})

    # 2. 路由
    for rf in required_files:
        if "route" in rf.get("template", ""):
            order.append({**rf, "step": 2, "action": "create"})

    # 3. 注册路由
    if required_files:
        order.append(
            {
                "path": "routes/route_registry.py",
                "action": "modify",
                "step": 3,
                "reason": "注册新路由到 route_registry.py",
            }
        )

    # 4. 测试
    if "tests" in str(touches) or any("test" in rf.get("template", "") for rf in required_files):
        order.append(
            {
                "path": "tests/test_{resource}.py",
                "action": "create",
                "step": 4,
                "reason": "集成测试",
            }
        )

    return order


def extract_patterns(reference_files: list, feature_desc: str) -> dict:
    """从参考文件中提取模式代码"""
    patterns = {}

    for ref in reference_files:
        full = PROJECT / ref
        if not full.exists():
            full2 = PROJECT / ref.replace("/", "\\")
            if not full2.exists():
                continue
            full = full2

        try:
            content = full.read_text("utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        # 提取路由装饰器
        route_patterns = []
        for line in content.split("\n"):
            m = re.match(r'^\s*@router\.(get|post|put|delete|ws)\(["\'](.+?)["\']', line)
            if m:
                route_patterns.append({"method": m.group(1).upper(), "path": m.group(2)})

        # 提取类定义
        classes = []
        for line in content.split("\n"):
            m = re.match(r"^class (\w+)", line)
            if m:
                classes.append(m.group(1))

        # 提取 import 模式
        imports = [l for l in content.split("\n") if l.startswith("from ") or l.startswith("import ")]

        patterns[ref] = {
            "routes": route_patterns[:5],
            "classes": classes[:5],
            "imports": imports[:10],
            "total_lines": len(content.split("\n")),
        }

    return patterns


def _section_involved_systems(touches: list) -> list[str]:
    lines = ["## 涉及系统"]
    lines.extend(f"- `{t}`" for t in touches)
    lines.append("")
    return lines


def _section_patterns(pattern_names: list) -> list[str]:
    lines = ["## 参考模式"]
    for p in pattern_names:
        if p in PATTERNS:
            lines.append(f"- **{p}**: {PATTERNS[p]['description']}")
    lines.append("")
    return lines


def _section_references(references: list, patterns: dict) -> list[str]:
    lines = ["## 参考文件"]
    for ref in references:
        if ref not in patterns:
            continue
        p = patterns[ref]
        routes_str = ", ".join(f"{r['method']} {r['path']}" for r in p["routes"])
        lines.append(f"- `{ref}` ({p['total_lines']} 行)")
        if routes_str:
            lines.append(f"  路由: {routes_str}")
    lines.append("")
    return lines


def _section_order(order: list) -> list[str]:
    lines = ["## 生成顺序"]
    for o in order:
        lines.append(f"  **Step {o['step']}**: {o['action'].upper()} `{o['path']}`")
        if "reason" in o:
            lines.append(f"  原因: {o['reason']}")
    lines.append("")
    return lines


def _section_templates(pattern_names: list) -> list[str]:
    lines = ["## 文件模板"]
    for p in pattern_names:
        if p not in PATTERNS or "file_template" not in PATTERNS[p]:
            continue
        tmpl = PATTERNS[p]["file_template"]
        lines.append(f"### 模板: {p}")
        lines.append(tmpl.strip())
        lines.append("")
    return lines


def _section_code_excerpts(references: list, patterns: dict) -> list[str]:
    lines = ["## 参考代码摘录"]
    for ref in references[:3]:
        if ref not in patterns:
            continue
        p = patterns[ref]
        lines.append(f"### {ref}: imports")
        for imp in p["imports"][:8]:
            lines.append(f"  {imp}")
        if p["routes"]:
            lines.append(f"### {ref}: 路由")
            for r in p["routes"][:5]:
                lines.append(f"  @router.{r['method']}({r['path']})")
        lines.append("")
    return lines


def generate_plan(feature_desc: str) -> str:
    """生成完整的特性规划报告"""
    analysis = analyze_feature(feature_desc)
    patterns = extract_patterns(analysis["references"], feature_desc)

    sections = [
        f"# 📋 特性生成规划: {feature_desc}",
        "",
        *_section_involved_systems(analysis["touches"]),
        *_section_patterns(analysis["patterns"]),
        *_section_references(analysis["references"], patterns),
        *_section_order(analysis["order"]),
        *_section_templates(analysis["patterns"]),
        *_section_code_excerpts(analysis["references"], patterns),
    ]
    return "\n".join(sections)


def main():
    if len(sys.argv) < 2:
        print('用法: python scripts/lima_feature_planner.py "描述"')
        sys.exit(1)

    desc = sys.argv[1]
    plan = generate_plan(desc)
    print(plan)

    # 保存到配置目录
    out = PROJECT / "feature-plan.md"
    out.write_text(plan, encoding="utf-8")
    log.info(f"\n✅ 规划已保存到 {out}")


if __name__ == "__main__":
    main()
