#!/usr/bin/env python3
"""
从 CodeGraph 93MB AST 数据库提取完整架构知识图谱。
包括: LiMa 核心 + esp32 固件 + 测试 + 包

生成:
1. Mermaid 模块依赖图
2. 关键调用链
3. 架构文档 → shared-memory

用法: python scripts/extract_codegraph_architecture.py
"""

import json
import logging
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("D:/QWEN3.0")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CODEGRAPH_DB = str(PROJECT_ROOT / ".codegraph" / "codegraph.db")

# 模块分类体系
MODULE_CATEGORIES = {
    "core": {
        "routes",
        "device_gateway",
        "device_intelligence",
        "device_memory",
        "device_voice",
        "device_workflow",
        "device_ledger",
        "device_ota",
        "device_policy",
        "device_logic",
        "device_support",
        "context_pipeline",
        "routing_loop",
        "routing_ml",
        "routing_selector",
        "provider_automation",
        "provider_inventory",
        "provider_probe",
        "response_cleaner",
        "session_memory",
        "search_gateway",
        "external_enrichment",
        "local_retrieval",
        "observability",
        "infra",
        "fleet",
        "monitor",
        "lima_mcp_stdio",
        "backends_registry",
        "tool_gateway",
        "routing_engine.py",
        "routing_classifier.py",
    },
    "firmware": {"esp32S_XYZ"},
    "test": {"tests"},
    "package": {"packages"},
    "code_context": {"code_context"},
    "ui": {"chat-web", "xiaozhi_drawing"},
    "script": {"scripts"},
}

# 反向: dir_name → category
DIR_CATEGORY = {}
for cat, dirs in MODULE_CATEGORIES.items():
    for d in dirs:
        DIR_CATEGORY[d] = cat


def connect():
    return sqlite3.connect(CODEGRAPH_DB)


def categorize_file(file_path: str) -> str:
    """将文件归入分类"""
    parts = Path(file_path).parts
    if not parts:
        return "other"
    top = parts[0]
    return DIR_CATEGORY.get(top, "other")


def get_module_summary():
    """按分类统计符号"""
    conn = connect()
    rows = conn.execute("SELECT file_path, kind, COUNT(*) as cnt FROM nodes GROUP BY file_path, kind").fetchall()
    conn.close()

    by_category = defaultdict(lambda: defaultdict(int))
    by_dir = defaultdict(lambda: defaultdict(int))

    for file_path, kind, cnt in rows:
        cat = categorize_file(file_path)
        by_category[cat][kind] += cnt

        top = Path(file_path).parts[0] if Path(file_path).parts else "?"
        by_dir[top][kind] += cnt

    return by_category, by_dir


def get_module_dependencies():
    """跨模块依赖分析（按分类）"""
    conn = connect()
    edges_raw = conn.execute("SELECT source, target, kind FROM edges WHERE kind='calls' OR kind='imports'").fetchall()
    conn.close()

    # 分类内和分类间依赖
    intra = defaultdict(lambda: defaultdict(int))
    inter = defaultdict(lambda: defaultdict(int))

    for src, tgt, kind in edges_raw:
        try:
            src_path = Path(src.split("::")[0].split(":")[0])
            tgt_path = Path(tgt.split("::")[0].split(":")[0])
            src_top = src_path.parts[0] if src_path.parts else "?"
            tgt_top = tgt_path.parts[0] if tgt_path.parts else "?"
        except (ValueError, IndexError):
            continue

        if src_top == tgt_top:
            intra[src_top][kind] += 1
        else:
            inter[(src_top, tgt_top)][kind] += 1

    return intra, inter


def get_key_call_chains():
    """完整调用链（不含 esp32 日志噪音）"""
    conn = connect()
    edges = conn.execute("SELECT source, target FROM edges WHERE kind='calls'").fetchall()
    conn.close()

    callee_counts = defaultdict(int)
    caller_map = defaultdict(list)

    for src, tgt in edges:
        callee_counts[tgt] += 1
        caller_map[tgt].append(src)

    # 过滤：跳过 esp32 的 log/debug 等噪音
    hot_nodes = sorted(callee_counts.items(), key=lambda x: -x[1])[:80]

    results = []
    conn2 = connect()
    seen = set()
    for node_id, count in hot_nodes:
        row = conn2.execute("SELECT name, qualified_name, file_path, kind FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not row:
            continue

        name = row[0]
        # 跳过噪音（日志/工具函数）
        if (
            name
            in (
                "_",
                "log",
                "debug",
                "info",
                "warn",
                "warning",
                "error",
                "bind",
                "get",
                "put",
                "t",
                "assert",
                "isBlank",
                "time",
                "post",
                "GetDeviceState",
            )
            and count > 100
        ):
            continue

        if name in seen:
            continue
        seen.add(name)
        file_path = row[2]
        cat = categorize_file(file_path)

        # 只看核心 + 固件
        if cat not in ("core", "firmware", "code_context"):
            continue

        callers = caller_map.get(node_id, [])
        caller_names = []
        for cid in callers[:5]:
            cname = conn2.execute("SELECT name FROM nodes WHERE id=?", (cid,)).fetchone()
            if cname:
                caller_names.append(cname[0])

        results.append(
            {
                "name": name,
                "kind": row[3],
                "file": file_path,
                "category": cat,
                "called_count": count,
                "callers": caller_names,
            }
        )

    conn2.close()
    return results


def generate_mermaid_diagram(inter_deps: dict) -> str:
    """生成分类间依赖 Mermaid 图"""
    lines = ["```mermaid", "graph TB"]
    added = set()

    # 按分类聚合
    cat_links = defaultdict(int)
    for (src, tgt), kinds in inter_deps.items():
        src_cat = DIR_CATEGORY.get(src, "other")
        tgt_cat = DIR_CATEGORY.get(tgt, "other")
        if src_cat != tgt_cat:
            total = sum(kinds.values())
            cat_links[(src_cat, tgt_cat)] += total

    for (src_cat, tgt_cat), count in sorted(cat_links.items(), key=lambda x: -x[1]):
        if count > 5:
            lines.append(f"  {src_cat} -->|{count}| {tgt_cat}")

    # 子模块间依赖（只显示核心里重要的）
    for (src, tgt), kinds in sorted(inter_deps.items(), key=lambda x: -sum(x[1].values())):
        total = sum(kinds.values())
        if total > 30 and src != tgt:
            lines.append(f"  {src}:::sub -->|{total}| {tgt}:::sub")

    lines.append("")
    lines.append("classDef sub fill:#e1f5fe,stroke:#0288d1")
    lines.append("classDef core fill:#e8f5e9,stroke:#43a047")
    lines.append("classDef firmware fill:#fff3e0,stroke:#f57c00")
    lines.append("classDef test fill:#fce4ec,stroke:#e53935")
    lines.append("```")
    return "\n".join(lines)


def generate_architecture_doc(by_category, by_dir, call_chains, inter_deps):
    """生成完整架构文档"""
    lines = []
    lines.append("# LiMa 全栈架构知识图谱")
    lines.append(f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"数据源: CodeGraph (40,760 节点, 84,332 关系)")
    lines.append("")

    # 整体结构
    lines.append("## 系统构成")
    lines.append("")
    for cat in ["core", "firmware", "test", "package", "code_context", "ui", "script"]:
        if cat in by_category:
            total = sum(by_category[cat].values())
            kinds = ", ".join(f"{k}={v}" for k, v in sorted(by_category[cat].items(), key=lambda x: -x[1])[:5])
            lines.append(f"- **{cat}**: {total} 符号 ({kinds})")

    lines.append("")

    # Mermaid 图
    lines.append("## 分类间依赖图")
    lines.append("")
    lines.append(generate_mermaid_diagram(inter_deps))

    lines.append("")

    # 目录详情
    lines.append("## 目录符号统计")
    lines.append("")
    for d in sorted(by_dir.keys(), key=lambda d: -sum(by_dir[d].values())):
        if d.startswith("esp32"):
            total = sum(by_dir[d].values())
            lines.append(f"- **{d}** (firmware): {total} 符号")
        elif d == "tests":
            total = sum(by_dir[d].values())
            lines.append(f"- **tests**: {total} 符号")
        elif d in MODULE_CATEGORIES.get("core", set()):
            total = sum(by_dir[d].values())
            lines.append(f"- **{d}**: {total} 符号")

    lines.append("")

    # 热点调用链
    lines.append("## 关键调用链 (Top 25)")
    lines.append("")
    for fn in call_chains[:25]:
        callers_str = ", ".join(fn["callers"][:5]) if fn["callers"] else "(入口)"
        lines.append(f"- **{fn['name']}** ({fn['kind']}) — [{fn['category']}] {fn['file']}")
        lines.append(f"  被调 {fn['called_count']} 次, 调用者: {callers_str}")

    lines.append("")

    # 固件-云端关键连接
    lines.append("## 设备-云端连接点")
    lines.append("")
    for fn in call_chains:
        if fn["category"] == "firmware":
            lines.append(f"- **{fn['name']}** → {fn['file']}")
            for r in call_chains:
                if r["category"] == "core" and r["name"] in fn.get("callers", []):
                    lines.append(f"  云端响应: {r['name']} ({r['file']})")

    return "\n".join(lines)


def main():
    log.info("🔍 从 CodeGraph 提取架构知识...")

    by_category, by_dir = get_module_summary()
    total = sum(sum(v.values()) for v in by_category.values())
    log.info(f"  总 {total} 符号, {len(by_category)} 分类")

    intra, inter = get_module_dependencies()

    log.info(f"  分类内关系: {sum(sum(v.values()) for v in intra.values())}")
    log.info(f"  跨分类关系: {sum(sum(v.values()) for v in inter.values())}")

    call_chains = get_key_call_chains()
    log.info(f"  热点函数: {len(call_chains)}")

    doc = generate_architecture_doc(by_category, by_dir, call_chains, inter)

    out_path = PROJECT_ROOT / "ARCHITECTURE_KNOWLEDGE.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    log.info(f"  ✅ 写入 {out_path} ({len(doc)} 字符)")

    # 摘要输出
    print("\n=== 系统构成 ===")
    for cat in ["core", "firmware", "test", "package", "code_context", "ui", "script"]:
        if cat in by_category:
            total_c = sum(by_category[cat].values())
            print(f"  {cat}: {total_c}")

    print("\n=== Top 目录 ===")
    for d in sorted(by_dir.keys(), key=lambda d: -sum(by_dir[d].values()))[:25]:
        print(f"  {d}: {sum(by_dir[d].values())}")

    print("\n=== 关键调用链 Top 12 ===")
    for fn in call_chains[:12]:
        print(f"  {fn['name']:20s} [{fn['category']:8s}] {fn['file'][:40]}")


if __name__ == "__main__":
    main()
