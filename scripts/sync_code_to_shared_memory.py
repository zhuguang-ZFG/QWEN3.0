#!/usr/bin/env python3
"""
LiMa → Shared Memory 同步器
将关键代码文件的 docstring + 模块摘要 嵌入 shared-memory ChromaDB。
这样 Cursor/Kimi 通过 shared-memory MCP 就能语义搜索项目代码。

用法: python scripts/sync_code_to_shared_memory.py [--rebuild]
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path("D:/QWEN3.0")
VECTOR_DIR = os.path.expanduser("~/.qclaw/vector-memory")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# 关键目录 — 只索引核心代码
KEY_DIRS = [
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
    "scripts",
    "tests",
    "lima_mcp_stdio",
]
EXCLUDE_DIRS = {"__pycache__", ".egg-info", ".venv", "node_modules"}


def get_code_entries():
    """从关键目录提取代码摘要"""
    entries = []
    for d in KEY_DIRS:
        dir_path = PROJECT_ROOT / d
        if not dir_path.exists():
            continue
        if dir_path.is_file():
            files = [dir_path]
        else:
            files = sorted(dir_path.rglob("*.py"))

        for py_file in files:
            # 跳过非代码目录
            if any(p.name in EXCLUDE_DIRS for p in py_file.parents):
                continue
            # 跳过 __init__ 和 conftest
            if py_file.name in {"__init__.py", "conftest.py"}:
                continue
            # 跳过大文件
            size = py_file.stat().st_size
            if size > 100 * 1024:
                continue

            try:
                source = py_file.read_text("utf-8", errors="replace")
            except Exception:
                continue

            rel = str(py_file.relative_to(PROJECT_ROOT))
            docstring, summary = extract_docstring(source, rel)

            if docstring:
                entries.append(
                    {
                        "path": rel,
                        "content": f"## {rel}\n\n{docstring}\n\n{summary}",
                        "title": rel,
                        "project": "LiMa",
                    }
                )

    return entries


def extract_docstring(source: str, path: str) -> tuple[str, str]:
    """提取模块文档字符串和摘要"""
    lines = source.split("\n")
    docstring_parts = []
    in_docstring = False
    quote_char = None
    module_docstring = ""
    summary_lines = []
    class_count = 0
    func_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 文档字符串
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                quote_char = stripped[:3]
                rest = stripped[3:]
                if rest.endswith(quote_char) and len(stripped) > 3:
                    docstring_parts.append(rest[:-3].strip())
                    in_docstring = False
                elif rest:
                    docstring_parts.append(rest.strip())
        else:
            if stripped.endswith(quote_char):
                docstring_parts.append(stripped[:-3].strip())
                in_docstring = False
            elif i > 30:  # 防止无限
                break
            else:
                docstring_parts.append(stripped)

        # 统计类和函数
        if stripped.startswith("class ") and not stripped.startswith("class _"):
            class_count += 1
        if (stripped.startswith("def ") or stripped.startswith("async def ")) and not stripped.startswith("def _"):
            func_count += 1

    if docstring_parts:
        module_docstring = " ".join(d for d in docstring_parts if d)[:800]
        summary_lines.append(f"模块摘要: {module_docstring[:200]}")

    summary_lines.append(f"类: {class_count}, 函数: {func_count}, 行数: {len(lines)}")
    return module_docstring, "\n".join(summary_lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    args = parser.parse_args()

    entries = get_code_entries()
    log.info(f"📦 提取 {len(entries)} 个代码条目")

    # 写入 shared-memory（通过 memory-bridge 的 JSON 输入格式）
    output = []
    for entry in entries:
        doc = {
            "id": f"code:{entry['path'].replace('/', ':')}:{hashlib.md5(entry['content'].encode()).hexdigest()[:8]}",
            "title": entry["title"],
            "content": entry["content"],
            "source": "codebase",
            "project": "LiMa",
            "type": "code_module",
        }
        output.append(doc)

    # 写 JSON 供 memory-bridge.py 导入
    out_path = PROJECT_ROOT / ".codebase-embed.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=1)

    log.info(f"✅ 写入 {out_path} ({len(output)} 条)")
    log.info(f"   接下来在 Cursor/Kimi 中通过 shared-memory MCP 的 search_memory 搜索代码")

    # 统计目录分布
    from collections import Counter

    dirs = Counter(entry["path"].split("/")[0] for entry in entries)
    log.info(f"\n📁 目录分布:")
    for d, c in dirs.most_common(10):
        log.info(f"   {d}: {c}")


if __name__ == "__main__":
    main()
