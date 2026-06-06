"""Telegram Knowledge commands — /save, /kb, /learn, /feed, /inbox.

All data stored on VPS (lima_sessions.db). Local is discardable cache only.
Stats/dashboard commands are in telegram_kb_stats.py (re-exported below).
"""

from __future__ import annotations

import logging

import telegram_bot

# Re-export stats/dashboard commands for backward compatibility
from routes.telegram_kb_stats import (
    _type_emoji,
)
from session_memory.store import search_memories_keyword
from session_memory.store_promote import save_typed_memory

_log = logging.getLogger(__name__)


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


async def cmd_learn(chat_id: str, args: str) -> None:
    """Show/approve learning candidates. Usage: /learn [approve|reject <id>]"""
    try:
        from session_memory.outcome_ledger import mark_learned, mark_rejected
        from session_memory.shadow_mode import list_candidates, update_candidate

        sub = args.strip().split()
        action = sub[0] if sub else "list"

        if action == "approve" and len(sub) > 1:
            candidate_id = sub[1]

            # 1. Get candidate details
            from session_memory.shadow_mode import list_candidates, update_candidate
            all_candidates = list_candidates(status="proposed") + list_candidates(status="approved")
            candidate = next((c for c in all_candidates if c["id"] == candidate_id), None)

            if candidate is None:
                await telegram_bot.send_message(
                    f"Candidate not found: `{candidate_id[:40]}`",
                    chat_id=chat_id, parse_mode="Markdown",
                )
                return

            # 2. Apply to routing weights
            weight_msg = ""
            cat = candidate.get("category", "")
            summary = candidate.get("summary", "")

            if cat == "routing_weight":
                try:
                    from context_pipeline.routing_weights import get_routing_weights
                    rw = get_routing_weights()

                    # Parse "Boost backend:scenario: X/Y ok" or "Degrade backend:scenario: X/Y ok"
                    parts = summary.split(":")
                    if len(parts) >= 2:
                        backend = parts[0].replace("Boost ", "").replace("Degrade ", "").strip()
                        scenario = parts[1].split()[0].strip() if len(parts) > 1 else "coding"

                        if "boost" in candidate_id.lower() or "Boost" in summary:
                            rw.record_success(backend, scenario)
                            stats = rw.get_stats(backend, scenario)
                            weight_msg = (
                                f"Boosted: `{backend}:{scenario}`\n"
                                f"  weight={stats['weight']:.2f} | "
                                f"success_rate={stats['success_rate']:.0%} | "
                                f"total={stats['successes']+stats['failures']}"
                            )
                        else:
                            rw.record_failure(backend, scenario)
                            stats = rw.get_stats(backend, scenario)
                            weight_msg = (
                                f"Degraded: `{backend}:{scenario}`\n"
                                f"  weight={stats['weight']:.2f} | "
                                f"success_rate={stats['success_rate']:.0%} | "
                                f"total={stats['successes']+stats['failures']}"
                            )
                except Exception as exc:
                    weight_msg = f"routing update failed: {type(exc).__name__}"

            # 3. Mark candidate as applied
            update_candidate(candidate_id, "applied", notes="telegram approval")

            # 4. Mark related outcomes as learned
            from session_memory.outcome_ledger import mark_learned, query
            related = query(limit=10)
            for item in related:
                if candidate_id.startswith(item["event_id"][:20]):
                    mark_learned(item["event_id"], notes="approved via Telegram")
                    break

            await telegram_bot.send_message(
                f"Approved: `{candidate_id[:50]}`\n"
                f"{weight_msg}\n"
                f"/digest for summary | /learn to review others",
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
    except Exception as exc:
        _log.debug("knowledge stats collection failed: %s", type(exc).__name__)

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
    except Exception as exc:
        _log.debug("knowledge stats collection failed: %s", type(exc).__name__)

    # Memory
    try:
        from session_memory.store_db import memory_stats
        ms = memory_stats()
        if ms.get("total"):
            lines.append(f"*Memory*: {ms['total']} entries, {ms['embedding_pct']}% embeddings")
            lines.append("")
    except Exception as exc:
        _log.debug("knowledge stats collection failed: %s", type(exc).__name__)

    if pending == 0:
        lines.append("All clear. Nothing needs attention.")
    else:
        lines.append(f"*{pending} items need attention*")
        lines.append("/learn | /digest | /outcome for details")

    await telegram_bot.send_message(
        "\n".join(lines)[:4000], chat_id=chat_id, parse_mode="Markdown",
    )
