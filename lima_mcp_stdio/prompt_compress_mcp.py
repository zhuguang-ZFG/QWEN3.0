#!/usr/bin/env python3
"""Prompt compression functions — zero-dependency text/code/JSON compressors."""

from __future__ import annotations

import json
import re


def _should_compress(text: str, min_chars: int = 200) -> tuple[bool, int]:
    """判断是否需要压缩，返回 (是否需要, 估算 token)"""
    tokens = max(1, len(text) // 4)
    return tokens >= min_chars // 4, tokens


# ========== 压缩器 ==========


def compress_text(text: str, target_ratio: float = 0.3, preserve_first_n: int = 3, preserve_last_n: int = 2) -> str:
    """压缩长文本：保留首N行+末M行 + 中间抽取关键句"""
    needs, tokens = _should_compress(text)
    if not needs:
        return text

    lines = text.split("\n")

    # 短文本直接返回
    if len(lines) <= 10:
        return text

    # 保留首 N 行
    head = lines[:preserve_first_n]

    # 保留末 M 行
    tail = lines[-preserve_last_n:] if preserve_last_n > 0 else []

    # 中间部分：抽取包含关键词的行（error/exception/warning/fail/import/def/class/route/@）
    keywords = re.compile(
        r"(error|exception|traceback|warning|fail|critical|timeout|"
        r"def\s|class\s|import\s|from\s|@|route|include|return|raise)",
        re.IGNORECASE,
    )
    middle = lines[preserve_first_n:-preserve_last_n] if preserve_last_n > 0 else lines[preserve_first_n:]

    # 提取关键行 + 非空行抽样
    key_lines = [l for l in middle if keywords.search(l)]
    non_empty = [l for l in middle if l.strip() and l not in key_lines]

    # 按比例抽样
    target_middle = max(5, int(len(middle) * target_ratio))
    sampled = key_lines
    remaining = target_middle - len(sampled)
    if remaining > 0 and non_empty:
        step = max(1, len(non_empty) // remaining)
        sampled += non_empty[::step][:remaining]

    # 组装
    result = head + sampled + tail
    summary = (
        f"\n[... compressed from {len(lines)} lines to {len(result)} lines "
        f"(ratio ~{max(1, int(len(result) / max(1, len(lines)) * 100))}%), "
        f"use detail=True to expand ...]\n"
    )

    return "\n".join(head) + "\n" + summary + "\n" + "\n".join(tail)


def _strip_docstrings(code: str) -> tuple[str, int]:
    """Remove multi-line docstrings (\"\"\" / ''') from code. Returns (code, removed_count)."""
    lines = code.split("\n")
    result = []
    in_docstring = False
    removed = 0
    for line in lines:
        stripped = line.strip()
        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
            removed += 1
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped.count('"""') == 1 and stripped.count("'''") == 1:
                in_docstring = True
                removed += 1
                continue
        result.append(line)
    return "\n".join(result), removed


def _strip_comments(code: str) -> tuple[str, int]:
    """Remove #-comment lines, preserving TODO/FIXME/HACK/XXX/NOTE/IMPORTANT. Returns (code, removed_count)."""
    lines = code.split("\n")
    result = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if re.search(r"(TODO|FIXME|HACK|XXX|NOTE|IMPORTANT)", stripped, re.IGNORECASE):
                result.append(line)
            else:
                removed += 1
            continue
        result.append(line)
    return "\n".join(result), removed


def _collapse_blanks(code: str) -> tuple[str, int]:
    """Collapse consecutive blank lines to at most 2. Returns (code, removed_count)."""
    lines = code.split("\n")
    result = []
    empty_count = 0
    removed = 0
    for line in lines:
        if line.strip():
            result.append(line)
            empty_count = 0
        else:
            empty_count += 1
            if empty_count <= 2:
                result.append(line)
            else:
                removed += 1
    return "\n".join(result), removed


def compress_code(code: str) -> str:
    """压缩代码：去注释/空行/简化文档字符串"""
    needs, tokens = _should_compress(code)
    if not needs:
        return code

    before = code
    code, doc_removed = _strip_docstrings(code)
    code, comment_removed = _strip_comments(code)
    code, blank_removed = _collapse_blanks(code)

    header = (
        f"\n/* compressed: removed {doc_removed} doc lines + "
        f"{comment_removed} comment lines + "
        f"{blank_removed} blank lines. "
        f"{len(before.splitlines())} -> {len(code.splitlines())} lines */\n"
    )
    return header + code


def compress_json(data_str: str, max_items: int = 8) -> str:
    """压缩 JSON/结构化数据：省略中间项，精简字段名，去 null"""
    needs, _ = _should_compress(data_str)
    if not needs:
        return data_str

    try:
        data = json.loads(data_str)
    except json.JSONDecodeError:
        return data_str

    def _compress_obj(obj, depth=0):
        if depth > 5:
            return "..."
        if isinstance(obj, dict):
            # 去掉值为 null/None/空列表/空字符串 的字段
            cleaned = {
                k: _compress_obj(v, depth + 1)
                for k, v in obj.items()
                if v is not None and v != [] and v != "" and v != {}
            }
            return cleaned
        elif isinstance(obj, list):
            if len(obj) > max_items:
                # 保留首尾各 N/2 个
                half = max_items // 2
                return obj[:half] + [f"... ({len(obj) - max_items} items omitted)"] + obj[-half:]
            return [_compress_obj(item, depth + 1) for item in obj]
        return obj

    compressed = _compress_obj(data)
    result = json.dumps(compressed, ensure_ascii=False, indent=2)
    return f"/* compressed: {len(data_str)} -> {len(result)} chars */\n{result}"


def compress_context(text: str) -> str:
    """智能上下文压缩：分析文本类型，选择最佳压缩策略"""
    needs, tokens = _should_compress(text)
    if not needs:
        return text

    # 判断类型
    is_code = bool(re.search(r"(^|\n)(def |class |import |from |@|# |/\*|-- )", text[:500]))
    is_json = text.strip().startswith("{") or text.strip().startswith("[")

    samples = text[:100]

    if is_json:
        return compress_json(text)
    elif is_code:
        return compress_code(text)
    else:
        # 文本类：根据不同场景调整参数
        # 日志 → 保留 error 行
        if re.search(r"(ERROR|WARN|TRACE|\[.*\]|\d{4}-\d{2}-\d{2})", samples):
            lines = text.split("\n")
            error_lines = [l for l in lines if re.search(r"(error|exception|traceback|warn|fail)", l, re.IGNORECASE)]
            if error_lines:
                return f"[... compressed: {len(lines)} lines -> {len(error_lines)} key lines ...]\n" + "\n".join(
                    error_lines
                )
        return compress_text(text)


# 从协议层导入，避免循环导入 — 协议层在运行时懒加载本模块的函数
from lima_mcp_stdio.prompt_compress_server import handle_request, main  # noqa: F401
