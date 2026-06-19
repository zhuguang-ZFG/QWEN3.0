"""LiMa Response Cleaner — 响应清洗模块.

从 http_caller.py 提取，负责：
- 品牌名替换（隐藏底层模型/供应商信息）
- 身份声明模式替换
- 后端错误消息检测
- 文本→工具调用提取（Kimi/Qwen 等文本输出工具调用的模型）
"""

from response_cleaner.core import _clean_brand_only, clean_response
from response_cleaner.error_detection import _is_backend_error
from response_cleaner.identity import _looks_like_self_identity, apply_identity_cleaning
from response_cleaner.patterns import BRAND_PATTERNS, CLEAN_PATTERNS, IDENTITY_PATTERNS
from response_cleaner.sanitizer import StreamIdentitySanitizer

__all__ = [
    "apply_identity_cleaning",
    "clean_response",
    "StreamIdentitySanitizer",
    "_is_backend_error",
    "_looks_like_self_identity",
    "_clean_brand_only",
    "BRAND_PATTERNS",
    "CLEAN_PATTERNS",
    "IDENTITY_PATTERNS",
]
