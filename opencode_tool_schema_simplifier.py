"""opencode_tool_schema_simplifier.py — 根据 OpenCode 版本动态简化工具 schema。

OpenCode 不同版本对工具 schema 的支持程度不同：
- v1.x: 基础工具支持，复杂 schema 可能导致解析错误
- v2.x: 完整 JSON Schema 支持，但仍建议简化以减少 token
- v3.x+: 支持嵌套 schema 和复杂类型

本模块根据客户端版本和后端能力动态调整工具 schema 的详细程度，平衡兼容性和 token 效率。

简化策略:
1. **描述压缩**: 删除冗长的 description，保留关键信息
2. **示例移除**: 删除 examples 字段（OpenCode 内置示例）
3. **可选字段折叠**: 将多个可选参数合并为一个 options 对象
4. **类型简化**: 复杂类型（oneOf/anyOf/allOf）简化为 object
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)

# 版本检测正则
VERSION_PATTERN = re.compile(r'OpenCode[/\s]+(\d+)\.(\d+)', re.IGNORECASE)


def parse_opencode_version(user_agent: str) -> tuple[int, int]:
    """从 User-Agent 中解析 OpenCode 版本。

    Returns:
        (major, minor) 元组，解析失败时返回 (2, 0)
    """
    if not user_agent:
        return (2, 0)

    match = VERSION_PATTERN.search(user_agent)
    if match:
        return (int(match.group(1)), int(match.group(2)))

    # 默认假设是 v2.0
    return (2, 0)


def should_simplify_for_backend(backend_name: str) -> bool:
    """判断后端是否需要简化 schema（弱后端通常需要简化）。"""
    # 已知对复杂 schema 支持较差的后端
    weak_schema_backends = {
        "longcat", "cf_llama4", "cfai_llama4",
        "ovh_", "pollinations", "local_",
    }

    return any(backend_name.startswith(prefix) for prefix in weak_schema_backends)


def simplify_description(description: str, max_length: int = 100) -> str:
    """压缩描述文本。"""
    if not description or len(description) <= max_length:
        return description

    # 保留第一句话
    first_sentence = description.split(". ")[0]
    if len(first_sentence) <= max_length:
        return first_sentence + "."

    # 截断到最大长度
    return description[:max_length].rsplit(" ", 1)[0] + "..."


def simplify_property(prop: Dict[str, Any], aggressive: bool = False) -> Dict[str, Any]:
    """简化单个属性定义。"""
    simplified = prop.copy()

    # 删除示例
    simplified.pop("examples", None)
    simplified.pop("example", None)

    # 压缩描述
    if "description" in simplified:
        simplified["description"] = simplify_description(
            simplified["description"],
            max_length=60 if aggressive else 100
        )

    # 删除格式约束（保留类型）
    if aggressive:
        simplified.pop("pattern", None)
        simplified.pop("format", None)
        simplified.pop("minLength", None)
        simplified.pop("maxLength", None)
