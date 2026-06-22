#!/usr/bin/env python3
"""
LiMa 代码索引器 — 将项目关键文件索引到 shared-memory ChromaDB。
供 Cursor/Kimi 做语义代码搜索。
用法: python scripts/codebase_indexer.py [--rebuild]
"""

import argparse
import hashlib
import os
import sys
import json

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Config
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

    "external_enrichment",
    "local_retrieval",
    "observability",
    "infra",
    "fleet",
    "monitor",
    "scripts",
    "tests",
    # MCP
    "lima_mcp_stdio",
]
EXCLUDE_WORDS = ["__pycache__", ".egg-info", ".git", ".venv"]
EXCLUDE_FILES = {"__init__.py", "conftest.py"}
MAX_FILE_SIZE = 50 * 1024  # 50KB


def scan_codebase():
    """Scan key dirs, extract .py file paths with module annotations."""
    files = []
    for d in KEY_DIRS:
        path = os.path.join(PROJECT_ROOT, d)
        if not os.path.isdir(path):
            continue
        for root, dirs, filenames in os.walk(path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_WORDS]
            for f in filenames:
                if not f.endswith(".py"):
                    continue
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                if os.path.getsize(full) > MAX_FILE_SIZE:
                    continue
                rel = os.path.relpath(full, PROJECT_ROOT)
                files.append(rel)
    return files


def extract_summary(filepath):
    """Extract first docstring/class/function from a .py file."""
    full = os.path.join(PROJECT_ROOT, filepath)
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(3000)  # Read first 3K chars
    except Exception:
        return None, ""

    # Extract module docstring
    lines = content.split("\n")
    summary_parts = []
    in_docstring = False
    docstring_lines = []
    classes = []
    functions = []

    for line in lines:
        stripped = line.strip()
        # Docstring
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if not in_docstring:
                in_docstring = True
                quote = stripped[:3]
                rest = stripped[3:]
                if rest.endswith(quote) and len(rest) > 3:
                    docstring_lines.append(rest[:-3].strip())
                    in_docstring = False
                else:
                    docstring_lines.append(rest.strip())
            else:
                if stripped.endswith('"""') or stripped.endswith("'''"):
                    docstring_lines.append(stripped[:-3].strip())
                    in_docstring = False
        elif in_docstring:
            docstring_lines.append(stripped)
        # Class/function
        elif stripped.startswith("class "):
            classes.append(stripped.split("(")[0].split(":")[0].replace("class ", ""))
        elif stripped.startswith("async def ") or stripped.startswith("def "):
            fn = stripped.replace("async def ", "").replace("def ", "")
            functions.append(fn.split("(")[0])

    summary = docstring_lines[:5] if docstring_lines else []
    if not summary and content:
        # First meaningful line
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith("from ") and not s.startswith("import "):
                summary.append(s[:80])
                break

    return "\n".join(summary), content[:2000] if summary else content[:2000]


def main():
    parser = argparse.ArgumentParser(description="Index LiMa codebase into shared memory")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild from scratch")
    args = parser.parse_args()

    print(f"🔍 Scanning {PROJECT_ROOT}...")
    files = scan_codebase()
    print(f"   Found {len(files)} Python files to index")

    # Build a manifest
    manifest = []
    for f in files:
        summary, preview = extract_summary(f)
        if summary:
            manifest.append(
                {
                    "path": f,
                    "summary": summary,
                    "hash": hashlib.md5(preview.encode()).hexdigest()[:12],
                }
            )
        else:
            manifest.append(
                {
                    "path": f,
                    "summary": f"(No docstring)",
                    "hash": "",
                }
            )

    # Write manifest for Cursor/Kimi to read
    manifest_path = os.path.join(PROJECT_ROOT, ".codebase-index.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"   Manifest written: {manifest_path}")
    print(f"   Total indexed: {len(manifest)} files")

    # Count by directory
    from collections import Counter

    dirs = Counter(os.path.dirname(f) for f in files)
    print(f"\n📁 目录分布 (Top 10):")
    for d, c in dirs.most_common(10):
        print(f"   {d}/: {c} files")

    print(f"\n✅ Done! Cursor/Kimi can now use .codebase-index.json for project-aware search.")


if __name__ == "__main__":
    main()
