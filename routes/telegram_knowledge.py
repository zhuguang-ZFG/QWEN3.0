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


async def cmd_outcome(chat_id: str, args: str) -> None:
    """Query Outcome Ledger. Usage: /outcome [source]"""
    try:
        from session_memory.outcome_ledger import query, stats

        source = args.strip()
        st = stats()
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
            lines.append("/outcome lima_code|ci|telegram|device_gateway for details")

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
        from agent_runtime.contracts import AGENT_CONTRACTS, STANDARD_PIPELINE, AgentRole, Stage

        lines = ["*Agent Contracts*", ""]

        # Pipeline
        lines.append("*Pipeline:*")
        for gate in STANDARD_PIPELINE:
            lines.append(f"  {gate.from_stage.value} → {gate.to_stage.value}"
                         f"{'  [approval]' if gate.requires_approval else ''}")
        lines.append("")

        # Roles
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


async def cmd_learn(chat_id: str, args: str) -> None:
    """Show/approve learning candidates. Usage: /learn [approve|reject <id>]"""
    try:
        from session_memory.outcome_ledger import mark_learned, mark_rejected
        from session_memory.shadow_mode import list_candidates, update_candidate

        sub = args.strip().split()
        action = sub[0] if sub else "list"

        if action == "approve" and len(sub) > 1:
            candidate_id = sub[1]

            # Mark in outcome_ledger (find the event)
            from session_memory.outcome_ledger import query
            related = query(limit=5)
            for item in related:
                if candidate_id.startswith(item["event_id"][:20]):
                    mark_learned(item["event_id"], notes=f"approved via Telegram")
                    break

            # Update candidate status
            updated = update_candidate(candidate_id, "approved", notes="telegram approval")

            # Try eval_gate if available
            gate_msg = ""
            try:
                from session_memory.eval_gate import approve_candidate
                approve_candidate(candidate_id)
                gate_msg = " | eval_gate approved"
            except ImportError:
                gate_msg = " | eval_gate not available"
            except Exception as exc:
                gate_msg = f" | eval_gate: {type(exc).__name__}"

            await telegram_bot.send_message(
                f"Approved: `{candidate_id[:50]}`\n"
                f"Ledger updated: {updated}{gate_msg}\n"
                f"/learn to review others | /digest for summary",
                chat_id=chat_id, parse_mode="Markdown",
            )
            return

        if action == "reject" and len(sub) > 1:
            candidate_id = sub[1]
            reason = " ".join(sub[2:]) if len(sub) > 2 else "manual rejection"
            update_candidate(candidate_id, "rejected", notes=reason[:200])

            # Also mark related outcome as rejected
            from session_memory.outcome_ledger import query
            related = query(limit=5)
            for item in related:
                if candidate_id.startswith(item["event_id"][:20]):
                    mark_rejected(item["event_id"], reason=reason[:200])
                    break

            await telegram_bot.send_message(
                f"Rejected: `{candidate_id[:50]}`",
                chat_id=chat_id, parse_mode="Markdown",
            )
            return

        # Default: list proposed candidates
        candidates = list_candidates(status="proposed")
        if not candidates:
            candidates = list_candidates(status="approved")[:3]

        if not candidates:
            await telegram_bot.send_message(
                "No pending learning candidates.\n/digest to scan for new patterns.",
                chat_id=chat_id, parse_mode="",
            )
            return

        lines = ["*Learning Candidates*", ""]
        for c in candidates[:8]:
            icon = "\U0001f7e2" if c["confidence"] >= 0.8 else "\U0001f7e1"
            lines.append(
                f"{icon} [{c['category']}] {c['summary'][:100]}\n"
                f"  evidence={c['evidence_count']} conf={c['confidence']} status={c['status']}\n"
                f"  `/learn approve {c['id'][:40]}`"
            )
            lines.append("")

        lines.append("/learn approve <id>  or  /learn reject <id>")
        await telegram_bot.send_message(
            "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Learn failed: {exc}", chat_id=chat_id, parse_mode="",
        )


async def cmd_feed(chat_id: str, args: str) -> None:
    """Search public experience sources. Usage: /feed <query> [--save]"""
    query = args.strip()
    save = False
    if query.endswith(" --save"):
        query = query[:-7].strip()
        save = True

    if not query:
        await telegram_bot.send_message(
            "/feed <query> [--save]\nSearch StackOverflow + GitHub Issues for public experience.\nAdd --save to store top results as typed memories.",
            chat_id=chat_id, parse_mode="",
        )
        return

    await telegram_bot.send_message(
        f"Searching: `{query[:60]}`...", chat_id=chat_id, parse_mode="Markdown",
    )

    try:
        from search_gateway.public_feeder import feed_experience

        result = feed_experience(query, limit=3, save_to_memory=save)
        items = result.get("results", [])
        saved = result.get("saved_count", 0)

        if not items:
            await telegram_bot.send_message(
                f"No results for: `{query[:60]}`", chat_id=chat_id, parse_mode="Markdown",
            )
            return

        lines = [f"*Feed: `{query[:40]}`* ({len(items)} results)", ""]
        for item in items[:5]:
            icon = {0.8: "\U0001f7e2", 0.5: "\U0001f7e1"}.get(
                round(item["confidence"] * 10) / 10 if item["confidence"] >= 0.8 else 0, "\U0001f534",
            )
            src = item["source"]
            lines.append(f"{icon} [{src}] {item['title'][:120]}")
            if item.get("url"):
                lines.append(f"  {item['url'][:80]}")

        if saved:
            lines.append(f"\nSaved {saved} memories. /kb to search.")

        await telegram_bot.send_message(
            "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
        )
    except Exception as exc:
        await telegram_bot.send_message(
            f"Feed failed: {exc}", chat_id=chat_id, parse_mode="",
        )


def _type_emoji(memory_type: str) -> str:
    return {
        "user_pref": "\U0001f464", "project_fact": "\U0001f4cb",
        "code_fact": "\U0001f4bb", "routing_lesson": "\U0001f9ed",
        "security_lesson": "\U0001f6e1", "reference_pattern": "\U0001f4d6",
        "test_result": "\U0001f9ea", "ops_event": "\U0001f6a8",
        "exchange": "\U0001f4ac", "compacted": "\U0001f4e6",
    }.get(memory_type, "\U0001f4be")


async def cmd_inbox(chat_id: str, args: str) -> None:
    """Unified inbox: tasks, learning, CI, devices — one view."""
    lines = ["*LiMa Inbox*", ""]
    pending = 0

    # Learning candidates
    try:
        from session_memory.shadow_mode import list_candidates
        candidates = list_candidates(status="proposed")
        if candidates:
            lines.append(f"*Learn* ({len(candidates)} pending)")
            for c in candidates[:3]:
                icon = "\U0001f7e2" if c["confidence"] >= 0.8 else "\U0001f7e1"
                lines.append(f"  {icon} {c['summary'][:80]}")
            pending += len(candidates)
            lines.append("")
    except Exception:
        pass

    # Outcome Ledger
    try:
        from session_memory.outcome_ledger import stats
        st = stats()
        unlearned = st.get("unlearned", 0)
        if unlearned:
            lines.append(f"*Outcomes* ({unlearned} unlearned)")
            lines.append(f"  Total: {st['total']} | Applied: {st.get('applied',0)} | Rejected: {st.get('rejected',0)}")
            pending += unlearned
            lines.append("")
    except Exception:
        pass

    # Memory
    try:
        from session_memory.store_db import memory_stats
        ms = memory_stats()
        if ms.get("total"):
            lines.append(f"*Memory*: {ms['total']} entries, {ms['embedding_pct']}% embeddings")
            lines.append("")
    except Exception:
        pass

    if pending == 0:
        lines.append("All clear. Nothing needs attention.")
    else:
        lines.append(f"*{pending} items need attention*")
        lines.append("/learn | /digest | /outcome for details")

    await telegram_bot.send_message(
        "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
    )
