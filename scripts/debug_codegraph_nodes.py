#!/usr/bin/env python3
"""Debug: find LiMa core nodes in CodeGraph"""

import sqlite3, os
from pathlib import Path

db = os.path.expanduser("D:/QWEN3.0/.codegraph/codegraph.db")
conn = sqlite3.connect(db)

# Find LiMa core files
LIMA_CORE = ["routes", "device_gateway", "device_intelligence", "routing_selector", "context_pipeline"]
for keyword in LIMA_CORE:
    rows = conn.execute(
        "SELECT id, name, kind, file_path FROM nodes WHERE file_path LIKE ? LIMIT 5", (f"%{keyword}%",)
    ).fetchall()
    if rows:
        for r in rows:
            print(f"  id={r[0][:60]}... name={r[1]} kind={r[2]} file={r[3]}")
    else:
        print(f"  {keyword}: 0 条")
    print()

# Check total by file
print("=== 按目录统计 ===")
dirs = {}
for (fp,) in conn.execute("SELECT DISTINCT substr(file_path,1, instr(file_path||'/','/')-1) FROM nodes").fetchall():
    if fp:
        cnt = conn.execute(f"SELECT COUNT(*) FROM nodes WHERE file_path LIKE '{fp}%'").fetchone()[0]
        dirs[fp] = cnt

for d, c in sorted(dirs.items(), key=lambda x: -x[1])[:30]:
    print(f"  {d}: {c}")

conn.close()
