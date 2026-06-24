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
        _log.warning("context_pipeline.skill_store not installed; backend recall disabled: %s", exc)
    return ""


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
    except ImportError as exc:
        _log.warning("context_pipeline.complexity not installed; complexity assessment disabled: %s", exc)
        return None
    except Exception as exc:
        _log.warning("complexity assessment failed: %s", exc, exc_info=True)
        return None


def auto_compress(messages: list[dict], backends: list[str], system_prompt: str) -> list[dict]:
    """自动压缩过长对话，防止超出后端上下文限制。"""
    try:
        from context_compressor import compress_messages, should_compress

        if backends and should_compress(messages, backends[0]):
            return compress_messages(messages, backends[0], system_prompt=system_prompt)
    except ImportError as exc:
        _log.warning("context_compressor not installed; auto compression disabled: %s", exc)
    return messages
