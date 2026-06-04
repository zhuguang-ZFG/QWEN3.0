"""context_compressor.py — Auto-compress long conversations for extended context.

When message history exceeds model's context window:
  1. Summarize early messages into a concise digest
  2. Keep recent messages + summary + system prompt
  3. Stay within backend token budget

Supports:
  - Token-aware compression (estimate via character count)
  - Per-backend context limits
  - Incremental compression (summarize in chunks)
"""
from __future__ import annotations

import logging
import os
from typing import Callable

_log = logging.getLogger(__name__)

# Conservative context limits (tokens) for known backends
# We estimate ~4 chars per token for mixed CN/EN text
BACKEND_CONTEXT_LIMITS: dict[str, int] = {
    "default": 4096,
    "longcat_chat": 32000,
    "longcat_lite": 16000,
    "longcat": 128000,
    "longcat_thinking": 64000,
    "github_gpt4o": 128000,
    "github_gpt4o_mini": 128000,
    "scnet_qwen30b": 32000,
    "scnet_qwen235b": 32000,
    "scnet_ds_flash": 128000,
    "scnet_ds_pro": 800000,
    "scnet_large_ds_flash": 128000,
    "scnet_large_ds_pro": 800000,
    "groq_llama70b": 128000,
    "cerebras_gptoss": 128000,
    # OpenCode stealth backends
    "opencode_stealth": 128000,
    "opencode_ds_flash": 128000,
}

# ~4 chars per token, reserve 20% for safety
CHARS_PER_TOKEN = 4
SAFETY_FACTOR = 0.8

# OpenCode multi-turn conversation settings
OPENCODE_KEEP_RECENT_TURNS = int(os.environ.get("LIMA_OPENCODE_KEEP_RECENT_TURNS", "8"))

# Compression prompt: summarize conversation so far
_COMPRESSION_PROMPT = (
    "Summarize the conversation above in 2-3 sentences. "
    "Focus on: what was asked, what was done, what decisions were made, "
    "and any important context for continuing. "
    "Keep technical details (file names, function names, error messages)."
)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token for mixed CN/EN text."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def get_context_limit(backend: str) -> int:
    """Get token budget for a backend. Returns token count."""
    return BACKEND_CONTEXT_LIMITS.get(backend, BACKEND_CONTEXT_LIMITS["default"])


def should_compress(
    messages: list[dict],
    backend: str,
    system_prompt: str = "",
) -> bool:
    """Check if message history exceeds backend context limit."""
    total = estimate_tokens(system_prompt)
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    total += estimate_tokens(str(block.get("text", ""))[:500])
    limit = get_context_limit(backend) * SAFETY_FACTOR
    return total > limit


def compress_messages(
    messages: list[dict],
    backend: str,
    system_prompt: str = "",
    summarize_fn: Callable | None = None,
    ide_source: str = "",
) -> list[dict]:
    """Compress message history to fit within backend context limit.

    Strategy:
      - Keep last N messages intact (N=4 for chat, N=OPENCODE_KEEP_RECENT_TURNS for OpenCode)
      - Summarize everything before that into a single system-like message
      - If no summarize_fn provided, do structural compression only
      - OpenCode: preserve tool_calls and tool results in recent turns

    Returns compressed messages list.
    """
    limit = get_context_limit(backend) * SAFETY_FACTOR

    # If already fits, return as-is
    if not should_compress(messages, backend, system_prompt):
        return messages

    _log.info(
        "Compressing %d messages for %s (limit=%d tokens)",
        len(messages), backend, limit,
    )

    # OpenCode: keep more recent turns to preserve tool call context
    if ide_source and "opencode" in ide_source.lower():
        keep_count = OPENCODE_KEEP_RECENT_TURNS
        _log.info(
            "OpenCode mode: keeping %d recent turns for tool context",
            keep_count,
        )
    else:
        keep_count = 4  # Keep last 4 messages intact
    if len(messages) <= keep_count + 2:
        # Not enough messages to compress meaningfully
        # Just truncate oldest content
        truncated = []
        total_tokens = estimate_tokens(system_prompt)
        for m in reversed(messages):
            content = m.get("content", "")
            if isinstance(content, str):
                t = estimate_tokens(content)
                if total_tokens + t > limit:
                    m = {**m, "content": content[: int((limit - total_tokens) * CHARS_PER_TOKEN)]}
                total_tokens += min(t, limit - total_tokens)
            truncated.insert(0, m)
            if total_tokens >= limit:
                break
        return truncated

    early = messages[:-keep_count]
    recent = messages[-keep_count:]

    # Build summary of early messages
    summary_parts = []
    early_tokens = 0
    for m in early:
        content = m.get("content", "")
        role = m.get("role", "user")
        if isinstance(content, str):
            snippet = content[:500]
        elif isinstance(content, list):
            snippet = " ".join(
                str(b.get("text", ""))[:200]
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            continue
        summary_parts.append(f"[{role}]: {snippet}")
        early_tokens += estimate_tokens(snippet)
        if early_tokens > 4000:
            summary_parts.append("... (earlier messages truncated)")
            break

    summary = (
        f"[Conversation Summary — {len(early)} earlier messages compressed]\n"
        + "\n".join(summary_parts[:20])
    )

    compressed = [{"role": "system", "content": summary}] + recent
    _log.info(
        "Compressed %d→%d messages (saved %d tokens)",
        len(messages), len(compressed),
        early_tokens,
    )
    return compressed


def estimate_context_usage(messages: list[dict], system_prompt: str = "") -> dict:
    """Estimate current context usage for monitoring."""
    tokens = estimate_tokens(system_prompt)
    per_msg = []
    for i, m in enumerate(messages):
        content = m.get("content", "")
        if isinstance(content, str):
            t = estimate_tokens(content)
        elif isinstance(content, list):
            t = sum(
                estimate_tokens(str(b.get("text", "")))
                for b in content
                if isinstance(b, dict)
            )
        else:
            t = 0
        tokens += t
        per_msg.append({"index": i, "role": m.get("role", "?"), "tokens": t})

    return {
        "total_tokens": tokens,
        "total_chars": tokens * CHARS_PER_TOKEN,
        "message_count": len(messages),
        "per_message": per_msg,
    }
