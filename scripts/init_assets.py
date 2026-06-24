"""Initialize built-in assets for the LiMa device app asset library."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from device_logic.db import connect
from device_logic.http import new_id, now

BUILTIN_ASSETS: list[dict[str, Any]] = [
    {
        "title": "你好世界",
        "category": "text",
        "content": "你好世界",
        "difficulty": "easy",
        "tags": ["问候"],
    },
    {
        "title": "生日快乐",
        "category": "text",
        "content": "生日快乐",
        "difficulty": "easy",
        "tags": ["祝福"],
    },
    {
        "title": "心形",
        "category": "svg",
        "content": "M50 30 C20 0 0 30 50 90 C100 30 80 0 50 30 Z",
        "difficulty": "easy",
        "tags": ["图形", "爱心"],
    },
    {
        "title": "五角星",
        "category": "svg",
        "content": "M50 5 L63 35 L95 35 L70 55 L80 85 L50 65 L20 85 L30 55 L5 35 L37 35 Z",
        "difficulty": "easy",
        "tags": ["图形"],
    },
]


def init_builtin_assets() -> None:
    """Insert built-in assets if they do not already exist by title+category."""
    with connect() as conn:
        for asset in BUILTIN_ASSETS:
            existing = conn.execute(
                "SELECT id FROM v2_asset_library WHERE title=? AND category=?",
                (asset["title"], asset["category"]),
            ).fetchone()
            if existing:
                continue
            tags = asset.get("tags", [])
            conn.execute(
                """
                INSERT INTO v2_asset_library
                (id, title, category, content, preview_url, tags, difficulty, created_at, use_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'active')
                """,
                (
                    new_id(),
                    asset["title"],
                    asset["category"],
                    asset["content"],
                    asset.get("preview_url", ""),
                    json.dumps(tags, ensure_ascii=False),
                    asset.get("difficulty", "easy"),
                    now(),
                ),
            )
        conn.commit()


if __name__ == "__main__":
    init_builtin_assets()
