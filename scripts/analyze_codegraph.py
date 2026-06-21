#!/usr/bin/env python3
"""分析 CodeGraph 数据库结构"""

import sqlite3, os

db = os.path.expanduser("D:/QWEN3.0/.codegraph/codegraph.db")
conn = sqlite3.connect(db)
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print(f"=== CodeGraph 数据库: {os.path.getsize(db) // 1024 // 1024}MB ===")
for (t,) in tables:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    except Exception:
        count = "?"
    # Schema
    schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'").fetchone()
    print(f"\n  📦 {t} ({count} 行)")
    if schema and schema[0]:
        # Show first 3 columns
        cols = [l.strip() for l in schema[0].split("\n") if l.strip()]
        for c in cols[:6]:
            print(f"     {c}")
conn.close()
