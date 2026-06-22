#!/usr/bin/env python3
"""
Prompt Compressor MCP — 零依赖，通用文本/代码/JSON 压缩。

工具：
- compress_text: 压缩长文本（提取关键句，去除冗余）
- compress_code: 压缩代码（去注释/空行/缩短标识符）
- compress_json: 压缩结构化数据（去 null/默认值，数组省略中间项）
- compress_context: 智能上下文压缩（全文分析，保留结构但极度精简）

所有工具自动判断是否值得压缩，短文本不作处理。
"""

import json
import re
import sys


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


def compress_code(code: str) -> str:
    """压缩代码：去注释/空行/简化文档字符串"""
    needs, tokens = _should_compress(code)
    if not needs:
        return code

    lines = code.split("\n")
    result = []
    in_docstring = False
    removed = {"doc_lines": 0, "comment_lines": 0, "empty_lines": 0}

    for line in lines:
        stripped = line.strip()

        # 文档字符串
        if in_docstring:
            if '"""' in stripped or "'''" in stripped:
                in_docstring = False
                removed["doc_lines"] += 1
            else:
                removed["doc_lines"] += 1
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped.count('"""') == 1 and stripped.count("'''") == 1:
                in_docstring = True
                removed["doc_lines"] += 1
                continue

        # 单行注释（保留重要注释）
        if stripped.startswith("#"):
            if re.search(r"(TODO|FIXME|HACK|XXX|NOTE|IMPORTANT)", stripped, re.IGNORECASE):
                result.append(line)
            else:
                removed["comment_lines"] += 1
            continue

        # 空行（保留最多连续2个）
        if not stripped:
            removed["empty_lines"] += 1
            continue

        result.append(line)

    # 合并空行（保留最大2个连续）
    final = []
    empty_count = 0
    for line in result:
        if line.strip():
            final.append(line)
            empty_count = 0
        else:
            empty_count += 1
            if empty_count <= 2:
                final.append(line)

    header = (
        f"\n/* compressed: removed {removed['doc_lines']} doc lines + "
        f"{removed['comment_lines']} comment lines + "
        f"{removed['empty_lines']} blank lines. "
        f"{len(code.splitlines())} -> {len(final)} lines */\n"
    )
    return header + "\n".join(final)


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


# ========== MCP 协议 ==========

TOOLS = {
    "compress_text": {
        "description": "压缩长文本/日志。保留首尾关键行 + 中间抽取含 error/warning 的关键句。短文本不处理。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要压缩的文本"},
                "target_ratio": {"type": "number", "description": "目标压缩比 (0.1-0.5)", "default": 0.3},
            },
            "required": ["text"],
        },
    },
    "compress_code": {
        "description": "压缩代码：去除注释/文档字符串/多余空行，保留 TODO/FIXME 等重要注释。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "要压缩的代码"},
            },
            "required": ["code"],
        },
    },
    "compress_json": {
        "description": "压缩 JSON/结构化数据：去 null/默认值，数组只保留首尾各 N 项，深度>5 截断。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_str": {"type": "string", "description": "JSON 字符串"},
                "max_items": {"type": "integer", "description": "数组保留最大项数", "default": 8},
            },
            "required": ["json_str"],
        },
    },
    "compress_context": {
        "description": "智能压缩：自动检测文本/代码/JSON/日志类型，选最优策略。通用入口。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "任意长文本"},
            },
            "required": ["text"],
        },
    },
}


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "prompt-compress", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": k, "description": v["description"], "inputSchema": v["inputSchema"]}
                    for k, v in TOOLS.items()
                ]
            },
        }

    if method == "tools/call":
        tool = req["params"]["name"]
        args = req["params"].get("arguments", {})
        try:
            if tool == "compress_text":
                text = compress_text(args["text"], args.get("target_ratio", 0.3))
            elif tool == "compress_code":
                text = compress_code(args["code"])
            elif tool == "compress_json":
                text = compress_json(args["json_str"], args.get("max_items", 8))
            elif tool == "compress_context":
                text = compress_context(args["text"])
            else:
                raise ValueError(f"Unknown tool: {tool}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req_id, "result": {}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp and "id" in resp and resp["id"] is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue


if __name__ == "__main__":
    main()
