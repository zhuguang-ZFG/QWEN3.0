"""opencode_skill_optimizer.py — OpenCode 专属 Skill 注入优化。

OpenCode 的系统提示已经内置了大量编码知识和最佳实践，LiMa 的通用 skill 可能与之重复。
本模块识别 OpenCode 已涵盖的 skill 类别，跳过注入或使用精简版本，减少 token 消耗。

优化策略:
1. **类别跳过**: OpenCode 已内置的类别（如 "style", "best-practices"）完全跳过
2. **精简注入**: 对于必要但部分重叠的类别，只注入关键点，删除示例代码
3. **上下文感知**: 根据请求类型（工具调用 vs 纯对话）动态调整注入深度

当前跳过的类别（来自 opencode_config.py）:
- "style": OpenCode 内置了 PEP 8、ESLint 等编码风格知识
- "security": OpenCode 有 OWASP、CVE 数据库集成（实验性）
- "performance": OpenCode 内置性能分析工具（Profiler）

未来可扩展:
- "testing": OpenCode 内置 pytest/jest 模板
- "documentation": OpenCode 自动生成 docstring
"""

from __future__ import annotations

import logging
import os
from typing import List, Dict, Optional

_log = logging.getLogger(__name__)

# 从 opencode_config 导入已跳过的类别
try:
    from opencode_config import OPENCODE_SKIPPED_SKILL_CATEGORIES
except ImportError:
    OPENCODE_SKIPPED_SKILL_CATEGORIES = {"style"}

# 精简策略配置
SKILL_SIMPLIFICATION_ENABLED = os.environ.get("LIMA_OPENCODE_SKILL_SIMPLIFY", "1") == "1"

# 需要精简的类别（保留核心，删除冗余）
SIMPLIFY_CATEGORIES = {
    "error-handling": {
        "keep": ["try-except patterns", "custom exceptions"],
        "remove": ["example code", "full traceback handling"],
    },
    "api-design": {
        "keep": ["REST principles", "versioning"],
        "remove": ["GraphQL examples", "full OpenAPI spec"],
    },
    "database": {
        "keep": ["SQL injection prevention", "transaction management"],
        "remove": ["ORM examples", "migration scripts"],
    },
}


def should_skip_skill(skill: Dict, ide_source: str, has_tools: bool) -> bool:
    """判断是否应该跳过某个 skill 的注入。

    Args:
        skill: skill 字典（包含 category、content 等）
        ide_source: IDE 来源（如 "OpenCode"）
        has_tools: 请求是否包含工具调用

    Returns:
        True 表示跳过，False 表示保留
    """
    if ide_source.lower() != "opencode":
        return False

    category = skill.get("category", "").lower()

    # 类别完全跳过
    if category in OPENCODE_SKIPPED_SKILL_CATEGORIES:
        _log.debug("skip skill (OpenCode built-in): %s", category)
        return True

    # 工具调用时跳过纯对话类 skill
    if has_tools and category in ("conversation", "tone", "empathy"):
        _log.debug("skip skill (tool mode): %s", category)
        return True

    return False


def simplify_skill_content(skill: Dict, category: str) -> Optional[str]:
    """精简 skill 内容（删除示例代码和冗余说明）。

    Args:
        skill: skill 字典
        category: skill 类别

    Returns:
        精简后的内容，如果不需要精简则返回 None
    """
    if not SKILL_SIMPLIFICATION_ENABLED:
        return None

    if category not in SIMPLIFY_CATEGORIES:
        return None

    content = skill.get("content", "")
    if not content:
        return None

    rules = SIMPLIFY_CATEGORIES[category]

    # 简单策略：提取标题和第一段，删除代码块
    lines = content.split("\n")
    simplified = []
    in_code_block = False

    for line in lines:
        # 检测代码块边界
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        # 跳过代码块内容
        if in_code_block:
            continue

        # 保留标题和核心内容
        if line.startswith("#") or any(kw in line.lower() for kw in rules["keep"]):
            simplified.append(line)
        # 跳过冗余内容
        elif any(kw in line.lower() for kw in rules["remove"]):
            continue
        # 保留普通段落（限制长度）
        elif line.strip():
            simplified.append(line)

    result = "\n".join(simplified[:20])  # 最多保留 20 行
    _log.debug("simplified skill: %s (%d → %d chars)", category, len(content), len(result))
    return result


def optimize_skills_for_opencode(
    skills: List[Dict],
    ide_source: str,
    has_tools: bool = False,
) -> List[Dict]:
    """为 OpenCode 优化 skill 注入列表。

    Args:
        skills: 原始 skill 列表
        ide_source: IDE 来源
        has_tools: 请求是否包含工具调用

    Returns:
        优化后的 skill 列表
    """
    if ide_source.lower() != "opencode":
        return skills

    optimized = []

    for skill in skills:
        category = skill.get("category", "").lower()

        # 检查是否应该跳过
        if should_skip_skill(skill, ide_source, has_tools):
            continue

        # 尝试精简内容
        simplified_content = simplify_skill_content(skill, category)
        if simplified_content:
            optimized_skill = skill.copy()
            optimized_skill["content"] = simplified_content
            optimized_skill["_simplified"] = True
            optimized.append(optimized_skill)
        else:
            optimized.append(skill)

    saved_count = len(skills) - len(optimized)
    if saved_count > 0:
        _log.info("OpenCode skill optimization: %d skipped, %d retained", saved_count, len(optimized))

    return optimized


def get_optimization_stats(original: List[Dict], optimized: List[Dict]) -> Dict:
    """计算优化统计信息（调试用）。"""
    original_size = sum(len(s.get("content", "")) for s in original)
    optimized_size = sum(len(s.get("content", "")) for s in optimized)

    return {
        "original_count": len(original),
        "optimized_count": len(optimized),
        "skipped_count": len(original) - len(optimized),
        "original_chars": original_size,
        "optimized_chars": optimized_size,
        "saved_chars": original_size - optimized_size,
        "saved_percent": round((1 - optimized_size / original_size) * 100, 1) if original_size > 0 else 0,
    }
