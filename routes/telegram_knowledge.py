"""Telegram Knowledge commands — /save, /kb, /memstats.

All data stored on VPS (lima_sessions.db). Local is discardable cache only.
"""

from __future__ import annotations

import telegram_bot
from session_memory.store import search_memories_keyword
from session_memory.store_db import memory_stats
from session_memory.store_promote import save_typed_memory


async def cmd_kb(chat_id: str, args: str) -> None:
    """Search memories by keyword. Usage: /kb <query>"""
    query = args.strip()
    if not query:
        await telegram_bot.send_message(
            "/kb <keyword>\nSearch typed memories by keyword.",
            chat_id=chat_id, parse_mode="",
        )
        return

    results = search_memories_keyword("_global", query[:80], limit=8)
    if not results:
        results = search_memories_keyword("_global", query[:80], limit=8)
    # Also search per-session
    from session_memory.store import get_recent_memories
    if not results:
        # Try broader search with fewer chars
        results = search_memories_keyword("_global", query.split()[0][:30], limit=5)

    if not results:
        await telegram_bot.send_message(
            f"No memories found for: `{query[:60]}`\nUse /save to add knowledge.",
            chat_id=chat_id, parse_mode="Markdown",
        )
        return

    lines = [f"*Knowledge: `{query[:40]}`* ({len(results)} results)", ""]
    for m in results[:8]:
        type_label = _type_emoji(m.memory_type) + " " + m.memory_type
        lines.append(f"{type_label}: {m.summary[:150]}")
        if m.detail:
            lines.append(f"  _{m.detail[:120]}_")
        lines.append("")

    text = "\n".join(lines)[:4000]
    await telegram_bot.send_message(text, chat_id=chat_id, parse_mode="Markdown")


async def cmd_save(chat_id: str, args: str) -> None:
    """Save a memory. Usage: /save <type>:<summary>

    Types: pref (user_pref), fact (project_fact), code (code_fact),
           route (routing_lesson), security (security_lesson),
           pattern (reference_pattern), test (test_result), ops (ops_event)

    Example: /save route: google_flash_lite works best for chat_fast scenarios
    """
    text = args.strip()
    if not text or ":" not in text:
        await telegram_bot.send_message(
            "/save <type>:<summary>\n"
            "Types: pref|fact|code|route|security|pattern|test|ops\n"
            "Example: /save route: google_flash_lite for chat_fast",
            chat_id=chat_id, parse_mode="",
        )
        return

    parts = text.split(":", 1)
    type_key = parts[0].strip().lower()
    summary = parts[1].strip()[:200] if len(parts) > 1 else ""

    if not summary:
        await telegram_bot.send_message("Summary required after :", chat_id=chat_id, parse_mode="")
        return

    type_map = {
        "pref": "user_pref", "fact": "project_fact", "code": "code_fact",
        "route": "routing_lesson", "security": "security_lesson",
        "pattern": "reference_pattern", "test": "test_result", "ops": "ops_event",
    }
    memory_type = type_map.get(type_key, "reference_pattern")

    try:
        save_typed_memory(
            memory_type=memory_type,
            summary=summary,
            detail=f"via Telegram /save {type_key}",
            session_id="_global",
        )
        emoji = _type_emoji(memory_type)
        await telegram_bot.send_message(
            f"{emoji} Saved: `{memory_type}` — {summary[:150]}",
            chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Save failed: {exc}", chat_id=chat_id, parse_mode="",
        )


async def cmd_memstats(chat_id: str, args: str) -> None:
    """Show memory statistics."""
    try:
        stats = memory_stats()
        lines = [
            "*Memory Stats*",
            f"  Total: {stats['total']} entries",
            f"  Sessions: {stats['sessions']}",
            f"  Embeddings: {stats['embedding_pct']}%",
            f"",
            "*By Type:*",
        ]
        for mem_type, count in stats["by_type"].items():
            emoji = _type_emoji(mem_type)
            lines.append(f"  {emoji} {mem_type}: {count}")
        await telegram_bot.send_message(
            "\n".join(lines), chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Stats failed: {exc}", chat_id=chat_id, parse_mode="",
        )


def _type_emoji(memory_type: str) -> str:
    return {
        "user_pref": "\U0001f464", "project_fact": "\U0001f4cb",
        "code_fact": "\U0001f4bb", "routing_lesson": "\U0001f9ed",
        "security_lesson": "\U0001f6e1", "reference_pattern": "\U0001f4d6",
        "test_result": "\U0001f9ea", "ops_event": "\U0001f6a8",
        "exchange": "\U0001f4ac", "compacted": "\U0001f4e6",
    }.get(memory_type, "\U0001f4be")
