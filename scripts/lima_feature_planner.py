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


def analyze_feature(feature_desc: str) -> dict:
    """分析特性描述，提取关键词、判断文件类型、定位参考"""

    desc_lower = feature_desc.lower()

    result = {
        "feature": feature_desc,
        "touches": [],  # 涉及的系统
        "required_files": [],  # 需要新建的文件
        "modify_files": [],  # 需要修改的文件
        "order": [],  # 生成顺序
        "references": [],  # 参考文件
        "patterns": [],  # 模式名
    }

    # === 关键词分析 ===

    # OTA/固件更新
    if any(k in desc_lower for k in ("ota", "固件", "升级", "firmware", "release", "版本")):
        result["touches"].append("device_ota")
        result["required_files"].append(
            {
                "path": "routes/{resource}.py",
                "template": "device_route",
                "reason": "设备端 OTA API 端点",
            }
        )
        result["references"].append("routes/device_ota.py")
        result["references"].append("device_ota/release.py")
        result["references"].append("tests/test_device_ota.py")
        result["patterns"].append("device_route")

    # 路由/API
    if any(k in desc_lower for k in ("路由", "端点", "api", "端点", "endpoint", "接口", "interface")):
        result["touches"].append("routes")
        result["patterns"].append("route")
        if not result["required_files"]:
            result["references"].append("routes/device_ota.py")

    # 设备功能
    if any(k in desc_lower for k in ("设备", "device", "gateway", "连接", "连接", "session")):
        result["touches"].append("device_gateway")
        result["references"].append("device_gateway/sessions.py")
        result["references"].append("device_gateway/task_service.py")

    # AI 后端
    if any(k in desc_lower for k in ("后端", "backend", "provider", "模型", "model", "ai")):
        result["touches"].append("routing_selector")
        result["references"].append("routing_selector/filters.py")
        result["references"].append("routing_selector/helpers.py")
        result["touches"].append("provider_inventory")
        result["touches"].append("backends_registry")

    # 测试
    if any(k in desc_lower for k in ("测试", "test", "集成", "集成测试")):
        result["patterns"].append("test_pattern")

    # 服务类
    if any(k in desc_lower for k in ("服务", "service", "管理", "manager", "handler")):
        result["patterns"].append("service_class")
        result["references"].append("device_gateway/task_service.py")

    # === 去重 ===
    result["references"] = list(dict.fromkeys(result["references"]))
    result["patterns"] = list(dict.fromkeys(result["patterns"]))
    result["touches"] = list(dict.fromkeys(result["touches"]))

    # === 确定文件路径 ===
    for rf in result["required_files"]:
        path = rf["path"]
        if "{resource}" in path:
            resource = feature_desc.lower().replace(" ", "_")[:20]
            rf["path"] = path.replace("{resource}", resource)

    # === 生成顺序 (依赖排序) ===
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


def generate_plan(feature_desc: str) -> str:
    """生成完整的特性规划报告"""

    analysis = analyze_feature(feature_desc)
    patterns = extract_patterns(analysis["references"], feature_desc)

    lines = []
    lines.append(f"# 📋 特性生成规划: {feature_desc}")
    lines.append("")

    # 涉及系统
    lines.append("## 涉及系统")
    for t in analysis["touches"]:
        lines.append(f"- `{t}`")
    lines.append("")

    # 参考模式
    lines.append("## 参考模式")
    for p in analysis["patterns"]:
        if p in PATTERNS:
            lines.append(f"- **{p}**: {PATTERNS[p]['description']}")
    lines.append("")

    # 参考文件
    lines.append("## 参考文件")
    for ref in analysis["references"]:
        if ref in patterns:
            p = patterns[ref]
            routes_str = ", ".join(f"{r['method']} {r['path']}" for r in p["routes"])
            lines.append(f"- `{ref}` ({p['total_lines']} 行)")
            if routes_str:
                lines.append(f"  路由: {routes_str}")
    lines.append("")

    # 生成顺序
    lines.append("## 生成顺序")
    for o in analysis["order"]:
        lines.append(f"  **Step {o['step']}**: {o['action'].upper()} `{o['path']}`")
        if "reason" in o:
            lines.append(f"  原因: {o['reason']}")
    lines.append("")

    # 文件模板
    lines.append("## 文件模板")
    for p in analysis["patterns"]:
        if p in PATTERNS and "file_template" in PATTERNS[p]:
            tmpl = PATTERNS[p]["file_template"]
            lines.append(f"### 模板: {p}")
            lines.append(tmpl.strip())
            lines.append("")

    # 参考代码摘录
    lines.append("## 参考代码摘录")
    for ref in analysis["references"][:3]:
        if ref in patterns:
            p = patterns[ref]
            lines.append(f"### {ref}: imports")
            for imp in p["imports"][:8]:
                lines.append(f"  {imp}")
            if p["routes"]:
                lines.append(f"### {ref}: 路由")
                for r in p["routes"][:5]:
                    lines.append(f"  @router.{r['method']}({r['path']})")
            lines.append("")

    return "\n".join(lines)


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
