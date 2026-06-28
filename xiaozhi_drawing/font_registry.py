"""字体注册表：扫描字体目录并按名称解析字体路径。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SUPPORTED_EXTS = (".ttf", ".otf", ".woff", ".woff2")
_DEFAULT_FONT_NAME = "LxgwWenKai.ttf"


def _fonts_dir() -> Path:
    """返回字体目录（环境变量优先，默认在 xiaozhi_drawing/fonts）。"""
    env = os.environ.get("LIMA_HANDWRITING_FONTS_DIR", "").strip()
    return Path(env) if env else Path(__file__).parent / "fonts"


def _default_font_path() -> Path:
    """默认字体路径（兼容旧 LIMA_HANDWRITING_FONT 单文件配置）。"""
    env = os.environ.get("LIMA_HANDWRITING_FONT", "").strip()
    if env:
        return Path(env)
    return _fonts_dir() / _DEFAULT_FONT_NAME


def list_handwriting_fonts() -> list[str]:
    """扫描字体目录，返回可用字体名列表（不含扩展名）。"""
    fonts_dir = _fonts_dir()
    if not fonts_dir.exists():
        return []
    return sorted({p.stem for p in fonts_dir.iterdir() if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTS})


def _match_font(font_name: str) -> Path | None:
    """按名称在字体目录中匹配字体文件；支持精确文件名或 stem。"""
    fonts_dir = _fonts_dir()
    if not fonts_dir.exists():
        return None
    target = font_name.lower()
    candidates = [p for p in fonts_dir.iterdir() if p.is_file()]
    for p in candidates:
        if (p.name.lower() == target or p.stem.lower() == target) and p.suffix.lower() in _SUPPORTED_EXTS:
            return p
    for ext in _SUPPORTED_EXTS:
        path = fonts_dir / (font_name + ext)
        if path.exists():
            return path
    return None


def resolve_font_path(font_name: str | None = None, font_path: Path | str | None = None) -> Path:
    """解析最终字体路径。

    优先级：显式 font_path > font_name 匹配 > LIMA_HANDWRITING_FONT > 默认 LxgwWenKai.ttf。
    """
    if font_path is not None:
        return Path(font_path)
    if font_name is not None:
        matched = _match_font(font_name)
        if matched:
            return matched
        logger.warning("未找到字体 %r，回退默认字体", font_name)
    default = _default_font_path()
    if default.exists():
        return default
    available = list_handwriting_fonts()
    if available:
        return _fonts_dir() / (available[0] + _SUPPORTED_EXTS[0])
    return default
