"""Pre-select context injection helpers for routing_engine."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


def try_recall_backend(messages: list[dict], scenario: str) -> str:
    """从 skill store 尝试召回推荐后端。"""
    try:
        from context_pipeline.skill_store import get_skill_store

        recalled = get_skill_store().recall(messages, scenario)
        if recalled:
            return recalled.backend
    except ImportError as exc:
        _log.warning(
            "skill_store unavailable; backend recall from crystallized skills "
            "skipped. Reason: %s",
            exc,
        )
    return ""


def inject_coding_context(
    messages: list[dict], scenario: str, query: str,
) -> tuple[list[dict], str]:
    """为 coding 场景注入代码上下文和历史记忆。返回 (messages, code_context_text)。"""
    code_context_text = ""
    if scenario != "coding":
        return messages, code_context_text

    try:
        from context_pipeline.code_context_injection import scan_and_build_context

        code_context_text = scan_and_build_context(query, messages)
        if code_context_text:
            code_ctx_msg = {"role": "system", "content": code_context_text}
            if messages and messages[0].get("role") == "system":
                messages.insert(1, code_ctx_msg)
            else:
                messages.insert(0, code_ctx_msg)
    except Exception as e:
        _log.debug("code_context_injection failed: %s", e)

    try:
        from session_memory.store_promote import query_by_type

        memory_parts: list[str] = []
        for mt in ("code_fact", "routing_lesson"):
            for mem in query_by_type(mt, limit=3):
                memory_parts.append(f"[{mt}] {mem.summary}")
        if memory_parts:
            memory_ctx = "Past coding decisions:\n" + "\n".join(memory_parts)
            mem_msg = {"role": "system", "content": memory_ctx}
            insert_pos = 2 if messages and messages[0].get("role") == "system" else 1
            messages.insert(insert_pos, mem_msg)
    except Exception as exc:
        _log.debug("code_context memory promote failed: %s", type(exc).__name__)

    return messages, code_context_text


def assess_complexity(messages: list[dict], ide_source: str):
    """评估请求复杂度，返回 complexity info 或 None。"""
    try:
        from context_pipeline.complexity import assess_complexity

        raw_msgs = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            if isinstance(m, dict)
            else {"role": getattr(m, "role", ""), "content": getattr(m, "content", "")}
            for m in messages
        ]
        return assess_complexity(raw_msgs, ide=ide_source)
    except (ImportError, Exception):
        return None


def auto_compress(messages: list[dict], backends: list[str], system_prompt: str) -> list[dict]:
    """自动压缩过长对话，防止超出后端上下文限制。"""
    try:
        from context_compressor import compress_messages, should_compress

        if backends and should_compress(messages, backends[0]):
            return compress_messages(messages, backends[0], system_prompt=system_prompt)
    except ImportError as exc:
        _log.warning(
            "context_compressor unavailable; long conversations will not be "
            "auto-compressed and may exceed backend context limits. Reason: %s",
            exc,
        )
    return messages
