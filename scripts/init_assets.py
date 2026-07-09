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
        "id": "starter_star",
        "title": "星星",
        "category": "svg",
        "content": "M50 5 L63 35 L95 35 L70 55 L80 85 L50 65 L20 85 L30 55 L5 35 L37 35 Z",
        "difficulty": "easy",
        "tags": ["starter", "图形"],
    },
    {
        "id": "starter_house",
        "title": "小房子",
        "category": "svg",
        "content": "M10 60 L50 20 L90 60 L90 95 L10 95 Z M35 95 L35 70 L65 70 L65 95 Z",
        "difficulty": "easy",
        "tags": ["starter", "图形"],
    },
    {
        "id": "starter_tree",
        "title": "树",
        "category": "svg",
        "content": "M50 10 L70 50 L60 50 L75 80 L25 80 L40 50 L30 50 Z M45 80 L45 95 L55 95 L55 80 Z",
        "difficulty": "easy",
        "tags": ["starter", "图形"],
    },
    {
        "id": "starter_fish",
        "title": "鱼",
        "category": "svg",
        "content": "M20 50 Q40 20 70 35 Q90 45 90 50 Q90 55 70 65 Q40 80 20 50 Z M25 48 L15 40 L15 60 Z",
        "difficulty": "easy",
        "tags": ["starter", "图形"],
    },
    {
        "id": "starter_flower",
        "title": "花",
        "category": "svg",
        "content": "M50 35 m-8 0 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0 M50 43 L50 75 M35 55 L50 43 L65 55",
        "difficulty": "easy",
        "tags": ["starter", "图形"],
    },
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
            asset_id = asset.get("id")
            if asset_id:
                existing = conn.execute(
                    "SELECT id FROM v2_asset_library WHERE id=?",
                    (asset_id,),
                ).fetchone()
            else:
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
                    asset_id or new_id(),
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
