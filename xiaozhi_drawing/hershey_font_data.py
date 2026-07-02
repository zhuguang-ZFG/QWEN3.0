"""Hershey 单笔画字体数据。

源白 Dr. Allen Hershey (1967)，字符高度 21 单位（Y 轴向上，0 = 基线）。
数据存储在同目录 hershey_font_data.json 中，此处仅做加载和类型标注。

格式: GLYPHS[char] = (advance_width, strokes)
  strokes = list[list[tuple[x, y], ...]]
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent / "hershey_font_data.json"

with open(_DATA_PATH, encoding="utf-8") as _f:
    _raw: dict[str, list] = json.load(_f)

GLYPHS: dict[str, tuple[int, list[list[tuple[int, int]]]]] = {
    ch: (entry[0], [[tuple(p) for p in stroke] for stroke in entry[1]])
    for ch, entry in _raw.items()
}
