"""context_compressor.py — Auto-compress long conversations for extended context.

When message history exceeds model's context window:
  1. Summarize early messages into a concise digest
  2. Keep recent messages + summary + system prompt
  3. Stay within backend token budget

Supports:
  - Token-aware compression (estimate via character count)
  - Per-backend context limits
  - Incremental compression (summarize in chunks)
  - OpenCode hierarchical: oldest→summary, middle→compressed, recent→intact
  - Tool result summarization: compress long file reads to key lines
  - System prompt dedup: remove repeated system prompts in tool call loops
  - Backend-aware dynamic compression ratios
"""
from __future__ import annotations

import logging
from collections.abc import Callable

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

# OpenCode multi-turn conversation settings (imported from centralized config)
from opencode_config import OPENCODE_KEEP_RECENT_TURNS

# ── Tool output summarization ──────────────────────────────────────────────
# Max chars to keep per tool result (e.g., file reads can be 100K+ chars)
TOOL_OUTPUT_MAX_CHARS = 2000
# Tool names whose output should be truncated aggressively
SUMMARIZABLE_TOOLS = {"read", "read_file", "bash", "shell", "grep", "glob",
                      "webfetch", "websearch", "lsp", "list_dir"}

# ── System prompt dedup ───────────────────────────────────────────────────
# OpenCode sends system prompt in every request; duplicate detection
_MIN_DEDUP_LENGTH = 200  # Only dedup system prompts longer than this

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


def summarize_tool_result(content: str, tool_name: str = "") -> str:
    """Compress long tool output to key lines.

    For file reads: keep first 5 + last 3 lines and line count.
    For shell/grep output: keep first 10 lines, truncate rest.
    For generic long output: truncate to TOOL_OUTPUT_MAX_CHARS.

    Ported from OpenCode compaction.ts TOOL_OUTPUT_MAX_CHARS.
    """
    if len(content) <= TOOL_OUTPUT_MAX_CHARS:
        return content

    lines = content.split("\n")

    if tool_name in ("read", "read_file"):
        head = lines[:5]
        tail = lines[-3:] if len(lines) > 5 else []
        return "\n".join(head) + (
            f"\n... [{len(lines) - 8} lines omitted] ...\n" + "\n".join(tail)
            if tail else f"\n... [{len(lines) - 5} lines omitted] ..."
        )

    if tool_name in ("bash", "shell", "grep", "glob"):
        return "\n".join(lines[:10]) + (
            f"\n... [{len(lines) - 10} more lines] ..."
            if len(lines) > 10 else ""
        )

    # Generic truncation: keep first 2000 chars
    return content[:TOOL_OUTPUT_MAX_CHARS] + (
        f"\n... [{len(content) - TOOL_OUTPUT_MAX_CHARS} chars truncated] ..."
    )


def dedup_system_prompts(messages: list[dict]) -> list[dict]:
    """Remove duplicate system prompts in tool call conversation loops.

    OpenCode sends the full system prompt in every /v1/chat/completions request.
    When these accumulate in message history, they waste significant tokens.
    Keeps only the first occurrence of each unique system prompt.
    """
    seen_system: set[str] = set()
    result: list[dict] = []
    for msg in messages:
        if msg.get("role") != "system":
            result.append(msg)
            continue
        content = msg.get("content", "")
        if not isinstance(content, str) or len(content) < _MIN_DEDUP_LENGTH:
            result.append(msg)
            continue
        # Normalize for dedup (trim whitespace, use hash for long content)
        key = content.strip()[:500]
        if key in seen_system:
            _log.debug("Deduplicated system prompt (%d chars)", len(content))
            continue
        seen_system.add(key)
        result.append(msg)
    return result


def get_dynamic_compression_ratio(backend: str) -> float:
    """Get compression ratio based on backend context window size.

    Smaller context windows need more aggressive compression:
      - 4K window: compress 70% of older messages
      - 8K window: compress 50%
      - 16K window: compress 35%
      - 32K+ window: compress 20%
    """
    limit = get_context_limit(backend)
    if limit <= 4096:
        return 0.70
    if limit <= 8192:
        return 0.50
    if limit <= 16384:
        return 0.35
    return 0.20


def hierarchical_compress(
    messages: list[dict],
    backend: str,
    system_prompt: str = "",
    ide_source: str = "",
) -> list[dict]:
    """Three-tier hierarchical compression for OpenCode long conversations.

    Strategy:
      - Tier 3 (oldest 60%): summarized into a single compact system message
      - Tier 2 (middle 25%): tool outputs compressed (summarize_tool_result)
      - Tier 1 (recent 15%): kept intact for tool call context

    This mirrors OpenCode's own compaction.ts approach:
      - HEAD → summarized, TAIL (recent turns) → intact
      - Tool outputs truncated to TOOL_OUTPUT_MAX_CHARS (2K chars)
      - Protected tools (skill) not pruned
    """
    if len(messages) <= 6:
        return messages

    # Dedup first
    messages = dedup_system_prompts(messages)

    limit = get_context_limit(backend) * SAFETY_FACTOR
    ratio = get_dynamic_compression_ratio(backend)

    # Calculate split points
    total = len(messages)
    recent_keep = max(3, int(total * 0.15))

    # OpenCode: keep more recent turns for tool call context
    if ide_source and "opencode" in ide_source.lower():
        recent_keep = max(OPENCODE_KEEP_RECENT_TURNS, recent_keep)

    middle_end = total - recent_keep
    oldest_end = max(0, int(total * ratio))

    # Make sure we don't cut in the middle of tool call pairs
    # Walk back to find a safe split point (tool role or user role boundary)
    if oldest_end > 0:
        oldest_end = _find_safe_split(messages, oldest_end)
    if middle_end > oldest_end:
        middle_end = _find_safe_split(messages, middle_end)

    oldest = messages[:oldest_end]
    middle = messages[oldest_end:middle_end]
    recent = messages[middle_end:]

    if not oldest and not middle:
        return messages

    # Tier 3: Summarize oldest messages
    if oldest:
        summary_text = _build_compact_summary(oldest, limit)
        compressed = [{"role": "system", "content": summary_text}]
    else:
        compressed = []

    # Tier 2: Compress tool outputs in middle messages
    if middle:
        middle_compressed = _compress_tool_outputs(middle)
        compressed.extend(middle_compressed)

    # Tier 1: Recent messages kept intact
    compressed.extend(recent)

    _log.info(
        "Hierarchical compress %d→%d msgs (ratio=%.0f%%, backend=%s)",
        total, len(compressed), ratio * 100, backend,
    )
    return compressed


def _find_safe_split(messages: list[dict], split_point: int) -> int:
    """Walk back from split_point to find a safe boundary (tool or user role).

    Avoid splitting in the middle of assistant→tool pairs.
    """
    if split_point <= 0:
        return 0
    # Walk backwards to find user or tool message boundary
    for i in range(min(split_point, len(messages) - 1), max(split_point - 5, 0), -1):
        role = messages[i].get("role", "")
        if role in ("user", "tool"):
            return i
    return split_point


def _build_compact_summary(messages: list[dict], budget_tokens: int) -> str:
    """Build a compact summary from oldest messages.

    Extracts: user queries, key decisions, file paths, error messages.
    Budget: ~500 tokens for the summary itself.
    """
    parts: list[str] = []
    total_chars = 0
    max_chars = budget_tokens * CHARS_PER_TOKEN * 0.3  # Use 30% of budget for summary

    for m in messages:
        content = m.get("content", "")
        role = m.get("role", "?")
        if isinstance(content, str):
            snippet = content[:300]
        elif isinstance(content, list):
            snippet = " ".join(
                str(b.get("text", ""))[:150]
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            continue
        if not snippet.strip():
            continue
        parts.append(f"[{role}] {snippet}")
        total_chars += len(snippet)
        if total_chars > max_chars:
            parts.append(f"... ({len(messages) - len(parts)} more messages)")
            break

    return (
        f"[Compressed History — {len(messages)} messages summarized]\n"
        + "\n".join(parts[:30])
    )


def _compress_tool_outputs(messages: list[dict]) -> list[dict]:
    """Compress long tool outputs in middle tier messages.

    Detects tool role messages and applies summarize_tool_result to content.
    Also handles OpenAI-format tool results in content arrays.
    """
    result: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "tool" and isinstance(content, str) and len(content) > TOOL_OUTPUT_MAX_CHARS:
            tool_name = msg.get("name", "") or ""
            tool_call_id = msg.get("tool_call_id", "")
            summarized = summarize_tool_result(content, tool_name)
            result.append({
                **msg,
                "content": summarized,
                "_summarized": True,
            })
            _log.debug("Summarized tool output: %s (%d→%d chars)",
                       tool_name, len(content), len(summarized))
        elif isinstance(content, list):
            # Check for tool_call_id in content blocks (OpenAI format)
            compacted = []
            any_compressed = False
            for block in content:
                if isinstance(block, dict) and block.get("tool_call_id"):
                    block_text = block.get("text", "") or block.get("content", "")
                    if isinstance(block_text, str) and len(block_text) > TOOL_OUTPUT_MAX_CHARS:
                        compacted.append({
                            **block,
                            "text": summarize_tool_result(block_text, ""),
                            "_summarized": True,
                        })
                        any_compressed = True
                        continue
                compacted.append(block)
            if any_compressed:
                result.append({**msg, "content": compacted})
            else:
                result.append(msg)
        else:
            result.append(msg)
    return result


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

    # OpenCode: use hierarchical compression for tool call conversations
    if ide_source and "opencode" in ide_source.lower():
        _log.info("OpenCode mode: using hierarchical compression (%d msgs)", len(messages))
        return hierarchical_compress(messages, backend, system_prompt, ide_source)

    # Standard mode: keep last N messages intact
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
