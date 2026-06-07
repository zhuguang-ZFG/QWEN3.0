"""opencode_reasoning_budget.py — 根据任务复杂度自动调整 reasoning_effort。

OpenCode 支持 reasoning_effort 参数（low/medium/high），控制推理模型的思考深度。
本模块根据请求特征自动推荐合适的 reasoning budget，避免简单任务浪费 token。

任务复杂度评估维度:
1. **代码长度**: 长代码需要更深推理
2. **错误类型**: RuntimeError < SyntaxError < LogicError
3. **工具数量**: 多工具协作需要更多规划
4. **上下文大小**: 大上下文需要更强推理能力
5. **用户指令明确度**: 模糊指令需要更多探索

推荐策略:
- low: 简单修复、格式化、补全
- medium: 重构、调试、多文件操作
- high: 架构设计、复杂算法、多步推理
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

_log = logging.getLogger(__name__)


def estimate_code_complexity(content: str) -> int:
    """估算代码复杂度（0-10 分）。"""
    if not content:
        return 0

    score = 0

    # 代码长度
    lines = content.count("\n")
    if lines > 500:
        score += 3
    elif lines > 100:
        score += 2
    elif lines > 20:
        score += 1

    # 控制流复杂度
    control_keywords = ["if", "else", "elif", "for", "while", "try", "except", "match", "case"]
    for kw in control_keywords:
        score += min(content.count(f" {kw} "), 2)  # 最多加 2 分

    # 嵌套深度（简单估算）
    max_indent = max((len(line) - len(line.lstrip()) for line in content.split("\n")), default=0)
    if max_indent > 12:
        score += 2
    elif max_indent > 8:
        score += 1

    return min(score, 10)


def detect_error_severity(content: str) -> int:
    """检测错误严重程度（0-10 分）。"""
    score = 0

    # 错误类型
    error_patterns = {
        r"SyntaxError": 2,
        r"IndentationError": 1,
        r"NameError": 3,
        r"TypeError": 4,
        r"AttributeError": 4,
        r"ValueError": 3,
        r"RuntimeError": 5,
        r"LogicError": 7,
        r"SegmentationFault": 8,
        r"MemoryError": 8,
    }

    for pattern, weight in error_patterns.items():
        if re.search(pattern, content, re.IGNORECASE):
            score += weight

    # 堆栈深度
    traceback_lines = content.count("Traceback")
    score += min(traceback_lines * 2, 4)

    return min(score, 10)


def estimate_instruction_ambiguity(query: str) -> int:
    """估算指令模糊度（0-10 分）。"""
    if not query:
        return 0

    score = 0

    # 模糊词汇
    ambiguous_phrases = [
        "优化", "改进", "重构", "更好", "清理", "整理",
        "optimize", "improve", "refactor", "better", "clean", "enhance"
    ]
    for phrase in ambiguous_phrases:
        if phrase in query.lower():
            score += 2

    # 缺少具体目标
    if not any(kw in query.lower() for kw in ["fix", "add", "remove", "change", "update", "修复", "添加", "删除", "修改"]):
        score += 3

    # 疑问句（探索性）
    if "?" in query or "怎么" in query or "如何" in query or "how" in query.lower():
        score += 2

    return min(score, 10)


def recommend_reasoning_effort(
    query: str,
    messages: List[Dict],
    tools: Optional[List[Dict]] = None,
    current_effort: Optional[str] = None,
) -> str:
    """推荐 reasoning_effort 级别。

    Args:
        query: 用户查询
        messages: 消息历史
        tools: 工具列表
        current_effort: 当前设置的 effort（如果用户明确指定，则不覆盖）

    Returns:
        推荐的 effort: "low" / "medium" / "high"
    """
    # 如果用户明确指定，不覆盖
    if current_effort and current_effort in ("low", "medium", "high"):
        _log.debug("respect user reasoning_effort: %s", current_effort)
        return current_effort

    # 提取所有消息内容
    all_content = query + " " + " ".join(
        msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)
    )

    # 计算各维度得分
    code_score = estimate_code_complexity(all_content)
    error_score = detect_error_severity(all_content)
    ambiguity_score = estimate_instruction_ambiguity(query)

    # 工具数量得分
    tool_score = 0
    if tools:
        tool_count = len(tools)
        if tool_count > 10:
            tool_score = 3
        elif tool_count > 5:
            tool_score = 2
        elif tool_count > 0:
            tool_score = 1

    # 上下文大小得分
    context_score = 0
    total_tokens = len(all_content) // 4  # 粗略估算
    if total_tokens > 8000:
        context_score = 3
    elif total_tokens > 4000:
        context_score = 2
    elif total_tokens > 1000:
        context_score = 1

    # 加权总分
    total_score = (
        code_score * 1.5
        + error_score * 1.2
        + ambiguity_score * 1.0
        + tool_score * 1.0
        + context_score * 0.8
    )

    # 映射到 effort 级别
    if total_score >= 15:
        effort = "high"
    elif total_score >= 8:
        effort = "medium"
    else:
        effort = "low"

    _log.info(
        "reasoning_effort recommendation: %s (score=%.1f: code=%d, error=%d, ambiguity=%d, tools=%d, context=%d)",
        effort,
        total_score,
        code_score,
        error_score,
        ambiguity_score,
        tool_score,
        context_score,
    )

    return effort


def should_enable_reasoning(
    query: str,
    messages: List[Dict],
    backend: str,
) -> bool:
    """判断是否应该启用推理模式。

    某些简单任务不需要推理：
    - 代码格式化
    - 简单补全
    - 查询文档
    """
    # 非推理后端直接返回 False
    if "deepseek-r1" not in backend.lower() and "o1" not in backend.lower():
        return False

    # 简单任务关键词
    simple_tasks = [
        "format", "格式化", "prettier",
        "complete", "补全", "autocomplete",
        "doc", "文档", "documentation",
        "explain", "解释", "what is",
    ]

    query_lower = query.lower()
    if any(kw in query_lower for kw in simple_tasks):
        _log.debug("disable reasoning for simple task: %s", query[:50])
        return False

    # 代码行数少且无错误
    all_content = query + " ".join(
        msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str)
    )
    if all_content.count("\n") < 20 and "Error" not in all_content:
        _log.debug("disable reasoning for short code: %d lines", all_content.count("\n"))
        return False

    return True


def get_budget_token_estimate(effort: str) -> int:
    """估算 reasoning budget 的 token 消耗（参考值）。

    Anthropic extended thinking:
    - low: ~1000 tokens
    - medium: ~5000 tokens
    - high: ~32000 tokens
    """
    return {
        "low": 1000,
        "medium": 5000,
        "high": 32000,
    }.get(effort, 5000)
