"""Telegram Knowledge stats/dashboard commands — extracted from telegram_knowledge.py."""

from __future__ import annotations

import logging

import telegram_bot

_log = logging.getLogger(__name__)


def _type_emoji(memory_type: str) -> str:
    return {
        "routing_lesson": "🧭", "code_fact": "💻", "test_result": "✅",
        "user_preference": "⭐", "architectural_decision": "🏗️",
        "tool_usage": "🔧", "error_fix": "🐛",
    }.get(memory_type, "📝")


async def cmd_memstats(chat_id: str, args: str) -> None:
    """Show memory statistics."""
    try:
        from session_memory.store_db import memory_stats

        stats = memory_stats()
        lines = [
            "*Memory Stats*",
            f"  Total: {stats['total']} entries",
            f"  Sessions: {stats['sessions']}",
            f"  Embeddings: {stats['embedding_pct']}%",
            "",
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


async def cmd_outcome(chat_id: str, args: str) -> None:
    """Query Outcome Ledger. Usage: /outcome [source]"""
    try:
        from session_memory.outcome_ledger import query, stats

        source = args.strip()
        st = stats()
        items = []
        lines = [
            "*Outcome Ledger*",
            f"  Total: {st['total']} events | Unlearned: {st['unlearned']}",
            "",
        ]
        if source:
            items = query(source=source, limit=5)
            lines.append(f"*Latest {source}:*")
        else:
            lines.append("*By Source:*")
            for src, s in st["by_source"].items():
                lines.append(f"  {src}: {s['total']} ({s['success']} ok)")
            lines.append("")
            lines.append("/outcome lima|ci|telegram|device_gateway for details")

        for item in items[:5]:
            icon = "✅" if item["outcome"] == "success" else "❌"
            lines.append(f"  {icon} [{item['source']}] {item['summary'][:100]}")

        await telegram_bot.send_message(
            "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Outcome query failed: {exc}", chat_id=chat_id, parse_mode="",
        )


async def cmd_digest(chat_id: str, args: str) -> None:
    """Generate learning digest with improvement candidates."""
    try:
        from session_memory.shadow_mode import scan_for_candidates, format_digest

        candidates = scan_for_candidates()
        text = format_digest(candidates)
        await telegram_bot.send_message(
            text, chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Digest failed: {exc}", chat_id=chat_id, parse_mode="",
        )


async def cmd_contracts(chat_id: str, args: str) -> None:
    """Show Agent Contracts and Pipeline stages."""
    try:
        from agent_runtime.contracts import AGENT_CONTRACTS, STANDARD_PIPELINE

        lines = ["*Agent Contracts*", ""]

        lines.append("*Pipeline:*")
        for gate in STANDARD_PIPELINE:
            lines.append(f"  {gate.from_stage.value} → {gate.to_stage.value}"
                         f"{'  [approval]' if gate.requires_approval else ''}")
        lines.append("")

        lines.append("*Roles:*")
        for role, contract in AGENT_CONTRACTS.items():
            tools_n = len(contract.allowed_tools)
            evidence = ", ".join(contract.produces_evidence[:3])
            lines.append(f"  *{role.value}*: {tools_n} tools → {evidence}")

        lines.append("")
        lines.append("/contracts <role> for tool list")

        await telegram_bot.send_message(
            "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Contracts failed: {exc}", chat_id=chat_id, parse_mode="",
        )


async def cmd_dashboard(chat_id: str, args: str) -> None:
    """Unified dashboard: health, routing, memory, outcomes."""
    import time as _t
    lines = ["*LiMa Dashboard*", f"`{_t.strftime('%H:%M:%S')}`", ""]

    try:
        import urllib.request, json
        req = urllib.request.Request("http://127.0.0.1:8080/health")
        resp = urllib.request.urlopen(req, timeout=5)
        h = json.loads(resp.read())
        modules = [k for k, v in h.get("modules", {}).items() if v]
        lines.append(f"*Health*: {h['status']} | {len(modules)} modules")
        lines.append("")
    except Exception as exc:
        _log.debug("health check failed: %s", type(exc).__name__)
        lines.append("*Health*: N/A")
        lines.append("")

    try:
        from backends_registry import BACKENDS
        lines.append(f"*Backends*: {len(BACKENDS)} registered")
        lines.append("")
    except Exception as exc:
        _log.debug("kb stats collection failed: %s", type(exc).__name__)

    try:
        from session_memory.outcome_ledger import stats
        st = stats()
        lines.append(f"*Outcomes*: {st['total']} total | {st['unlearned']} unlearned | {st.get('applied',0)} applied")
        for src, s in st.get("by_source", {}).items():
            if s["total"] > 0:
                lines.append(f"  {src}: {s['success']}/{s['total']} ok")
        lines.append("")
    except Exception as exc:
        _log.debug("kb stats collection failed: %s", type(exc).__name__)

    try:
        from session_memory.store_db import memory_stats
        ms = memory_stats()
        lines.append(f"*Memory*: {ms['total']} entries | {ms['embedding_pct']}% embedded")
        lines.append("")
    except Exception as exc:
        _log.debug("kb stats collection failed: %s", type(exc).__name__)

    try:
        from lima_mcp.tool_defs import TOOL_DEFINITIONS
        lines.append(f"*MCP*: {len(TOOL_DEFINITIONS)} tools")
        lines.append("")
    except Exception as exc:
        _log.debug("kb stats collection failed: %s", type(exc).__name__)

    lines.append("/inbox pending | /digest learning | /outcome details")
    await telegram_bot.send_message(
        "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
    )
