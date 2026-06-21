#!/usr/bin/env python3
"""分析固件-云端连接点"""

import sqlite3
from collections import defaultdict
from pathlib import Path

db = "D:/QWEN3.0/.codegraph/codegraph.db"
conn = sqlite3.connect(db)

# 固件文件路径包含的关键词
FIRMWARE_PATTERNS = ["esp32", "firmware", "xiaozhi-esp32"]
CORE_DIRS = ["routes", "device_gateway", "device_intelligence"]


def is_firmware(path):
    return any(p in path for p in FIRMWARE_PATTERNS)


def is_core(path):
    return any(path.startswith(d) for d in CORE_DIRS)


# 查找固件调用核心代码的边
print("=== 固件 → 云端调用链 ===")
cross_edges = conn.execute("SELECT source, target, kind FROM edges WHERE kind='calls' OR kind='imports'").fetchall()

fw_to_core = defaultdict(int)
core_to_fw = defaultdict(int)

for src, tgt, kind in cross_edges:
    src_path = src.split("::")[0].split(":")[0]
    tgt_path = tgt.split("::")[0].split(":")[0]

    is_src_fw = is_firmware(src_path)
    is_tgt_fw = is_firmware(tgt_path)
    is_src_core = is_core(src_path)
    is_tgt_core = is_core(tgt_path)

    if is_src_fw and is_tgt_core:
        fw_to_core[tgt_path] += 1
    elif is_src_core and is_tgt_fw:
        core_to_fw[src_path] += 1

print(f"\n固件→云端 ({len(fw_to_core)} 关系)")
for path, cnt in sorted(fw_to_core.items(), key=lambda x: -x[1])[:15]:
    print(f"  {path}: {cnt}")

print(f"\n云端→固件 ({len(core_to_fw)} 关系)")
for path, cnt in sorted(core_to_fw.items(), key=lambda x: -x[1])[:15]:
    print(f"  {path}: {cnt}")

# 查找跨文件真实调用（非导入）
print("\n=== 跨分类真实调用 (calls) ===")
cross_calls = []
for src, tgt in conn.execute("SELECT source, target FROM edges WHERE kind='calls'"):
    src_path = src.split("::")[0].split(":")[0]
    tgt_path = tgt.split("::")[0].split(":")[0]
    src_cat = "firmware" if is_firmware(src_path) else ("core" if is_core(src_path) else "other")
    tgt_cat = "firmware" if is_firmware(tgt_path) else ("core" if is_core(tgt_path) else "other")
    if src_cat != tgt_cat:
        src_fun = src.split("::")[-1] if "::" in src else src.split(":")[-1] if ":" in src else "?"
        tgt_fun = tgt.split("::")[-1] if "::" in tgt else tgt.split(":")[-1] if ":" in tgt else "?"
        cross_calls.append((src_cat, src_fun, src_path, tgt_cat, tgt_fun, tgt_path))

for s_cat, s_fun, s_path, t_cat, t_fun, t_path in cross_calls[:30]:
    print(f"  {s_cat}:{s_fun}({s_path[:50]}) → {t_cat}:{t_fun}({t_path[:50]})")

conn.close()
