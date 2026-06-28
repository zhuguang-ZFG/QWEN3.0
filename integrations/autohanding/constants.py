"""Constants for autohanding.com handwriting preview API.

Source: reverse-engineered from https://www.autohanding.com/ frontend JS.
Only the free preview endpoint is used; paid download endpoints are not supported.
"""

from __future__ import annotations

PREVIEW_BASE_URL = "https://www.autohanding.com"
PREVIEW_TEXT_ENDPOINT = "/api/v1/handwrite-preview/convert-text"
PREVIEW_FILE_ENDPOINT = "/api/v1/handwrite-preview/convert"

DEFAULT_FONT_TYPE = "0"
DEFAULT_PAPER_BG_TYPE = "20"
DEFAULT_MISTAKE_RATE = 3
DEFAULT_MESSY_RATIO = 0
DEFAULT_CHAR_RANDOM = 0

MAX_TEXT_LENGTH = 3500

# Font options extracted from autohanding frontend.
FONT_OPTIONS: dict[str, str] = {
    "0": "栗壳坚坚体",
    "7": "平方洒脱体",
    "12": "硬笔楷书",
    "4": "新叶念体",
    "6": "手写体体1",
    "14": "真实-手写体2",
    "15": "真实-手写体3",
    "16": "真实-手写体4",
    "17": "真实-手写体5",
    "18": "真实-手写体6",
    "19": "真实-手写体7",
    "20": "真实-手写体8",
    "21": "真实-手写体9",
    "22": "真实-手写体10",
    "23": "真实-手写体11",
    "24": "真实-手写体12",
    "1015": "真实-手写体3-加粗",
    "1016": "真实-手写体4-加粗",
    "1017": "真实-手写体5-加粗",
    "1018": "真实-手写体6-加粗",
    "1019": "真实-手写体7-加粗",
    "1020": "真实-手写体8-加粗",
    "1021": "真实-手写体9-加粗",
    "1022": "真实-手写体10-加粗",
    "1023": "真实-手写体11-加粗",
    "1024": "真实-手写体12-加粗",
    "8": "王强手写体",
    "1": "喜脉喜欢体",
    "2": "ChillZhuo",
    "3": "pigtruman手写体",
    "13": "繁体-辰宇落雁体",
    "9": "日文-TekitouPoem",
    "10": "韩文-KimjungchulScript",
    "25": "其他语言",
}

# Paper background options extracted from autohanding frontend.
PAPER_BG_OPTIONS: dict[str, str] = {
    "41": "实拍-红格子稿纸 (400字/页)",
    "42": "可打印-黑格子稿纸 (400字/页)-高清",
    "43": "可打印-红格子稿纸 (400字/页)-高清",
    "20": "实拍-单红线信稿纸",
    "30": "可打印-单红线A4信稿纸-新",
    "0": "草稿纸-高清实拍",
    "1": "可打印-A4纸-纵向-600dpi高清 (4960×7015)",
    "2": "可打印-A4纸-横向-600dpi高清 (7015×4960)",
    "3": "可打印-B5纸-纵向-600dpi高清",
    "4": "可打印-B5纸-横向-600dpi高清",
    "5": "可打印-A3纸-纵向-600dpi高清",
    "6": "可打印-A3纸-横向-600dpi高清",
    "22": "可打印-单红线信稿纸-宽行距-新",
    "1001": "可打印-纵向A4-可处理表格 (内测中)",
    "1002": "可打印-横向A4-可处理表格 (内测中)",
    "1003": "可打印-纵向B5-可处理表格 (内测中)",
    "1004": "可打印-横向B5-可处理表格 (内测中)",
    "1005": "可打印-纵向A3-可处理表格 (内测中)",
    "1006": "可打印-横向A3-可处理表格 (内测中)",
}


def validate_font_type(value: str) -> str:
    """Return normalized font type or default if invalid."""
    return value if value in FONT_OPTIONS else DEFAULT_FONT_TYPE


def validate_paper_bg_type(value: str) -> str:
    """Return normalized paper background type or default if invalid."""
    return value if value in PAPER_BG_OPTIONS else DEFAULT_PAPER_BG_TYPE


def validate_rate(value: int | str, default: int = 0) -> int:
    """Clamp rate-like parameters to 0-100 range."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, v))
