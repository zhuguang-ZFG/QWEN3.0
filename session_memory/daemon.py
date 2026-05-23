"""Memory daemon — background inbox ingestion and periodic consolidation.

Runs as an asyncio background task, not in the request hot path.
Ingests files from data/memory_inbox/, extracts typed facts,
and periodically consolidates old memories into durable insights.
"""

import asyncio
import json
import os
import time
import logging

from session_memory.store import (
    save_typed_memory, query_by_type, count_memories, MEMORY_TYPES,
)

logger = logging.getLogger(__name__)

INBOX_DIR = os.environ.get(
    "LIMA_MEMORY_INBOX", os.path.join(os.path.dirname(__file__), "..", "data", "memory_inbox")
)
CONSOLIDATION_INTERVAL = int(os.environ.get("LIMA_MEMORY_CONSOLIDATION_INTERVAL", "300"))
CONSOLIDATION_THRESHOLD = 20

_running = False


async def start_daemon() -> None:
    """Start the memory daemon as a background task."""
    global _running
    if _running:
        return
    _running = True
    logger.info("[MemoryDaemon] started, inbox=%s, interval=%ds", INBOX_DIR, CONSOLIDATION_INTERVAL)
    asyncio.create_task(_daemon_loop())


async def _daemon_loop() -> None:
    global _running
    while _running:
        try:
            _ingest_inbox()
            _consolidate_if_needed()
        except Exception as e:
            logger.warning("[MemoryDaemon] cycle error: %s", e)
        await asyncio.sleep(CONSOLIDATION_INTERVAL)


def stop_daemon() -> None:
    global _running
    _running = False


def _ingest_inbox() -> int:
    """Scan inbox dir for .md/.json files, extract typed memories, archive processed."""
    if not os.path.isdir(INBOX_DIR):
        return 0

    ingested = 0
    for fname in os.listdir(INBOX_DIR):
        fpath = os.path.join(INBOX_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        if not fname.endswith((".md", ".json", ".txt")):
            continue

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read(8192)
            memories = _extract_facts(fname, content)
            for mem_type, summary in memories:
                save_typed_memory(memory_type=mem_type, summary=summary)
                ingested += 1
            _archive_file(fpath)
        except Exception as e:
            logger.warning("[MemoryDaemon] ingest %s failed: %s", fname, e)

    if ingested:
        logger.info("[MemoryDaemon] ingested %d memories from inbox", ingested)
    return ingested


def _extract_facts(fname: str, content: str) -> list[tuple[str, str]]:
    """Extract typed memory facts from a file's content."""
    facts = []

    if fname.endswith(".json"):
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for item in data[:20]:
                    if isinstance(item, dict) and "summary" in item:
                        mt = item.get("type", "project_fact")
                        facts.append((mt, item["summary"][:200]))
            elif isinstance(data, dict) and "summary" in data:
                mt = data.get("type", "project_fact")
                facts.append((mt, data["summary"][:200]))
        except json.JSONDecodeError:
            pass
        return facts

    # Markdown/text: extract lines starting with "- " as facts
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") and len(line) > 5:
            summary = line[2:].strip()[:200]
            mem_type = _classify_line(summary)
            facts.append((mem_type, summary))
            if len(facts) >= 20:
                break

    return facts


def _classify_line(text: str) -> str:
    """Heuristic classification of a memory line."""
    t = text.lower()
    if any(w in t for w in ["deploy", "restart", "backup", "server"]):
        return "ops_event"
    if any(w in t for w in ["test", "passed", "failed", "coverage"]):
        return "test_result"
    if any(w in t for w in ["route", "backend", "fallback", "health"]):
        return "routing_lesson"
    if any(w in t for w in ["vuln", "auth", "token", "secret", "xss"]):
        return "security_lesson"
    if any(w in t for w in ["pattern", "reference", "library"]):
        return "reference_pattern"
    if any(w in t for w in ["prefer", "user", "style", "want"]):
        return "user_pref"
    if any(w in t for w in ["def ", "class ", "import ", "function"]):
        return "code_fact"
    return "project_fact"


def _archive_file(fpath: str) -> None:
    """Move processed file to .processed/ subdirectory."""
    processed_dir = os.path.join(os.path.dirname(fpath), ".processed")
    os.makedirs(processed_dir, exist_ok=True)
    dest = os.path.join(processed_dir, os.path.basename(fpath))
    os.replace(fpath, dest)


def _consolidate_if_needed() -> None:
    """Consolidate old memories when threshold is exceeded."""
    conn = None
    try:
        from session_memory.store import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM memories"
        ).fetchall()
        for (sid,) in rows:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE session_id = ?", (sid,)
            ).fetchone()[0]
            if count > CONSOLIDATION_THRESHOLD:
                _consolidate_session(conn, sid)
    except Exception as e:
        logger.warning("[MemoryDaemon] consolidation error: %s", e)
    finally:
        if conn:
            conn.close()


def _consolidate_session(conn, session_id: str) -> None:
    """Merge oldest exchange memories into a single compacted entry."""
    oldest = conn.execute(
        "SELECT id, summary FROM memories "
        "WHERE session_id = ? AND memory_type = 'exchange' "
        "ORDER BY timestamp ASC LIMIT 10",
        (session_id,),
    ).fetchall()
    if len(oldest) < 5:
        return

    ids = [r[0] for r in oldest]
    summaries = [r[1] for r in oldest]
    merged = "; ".join(summaries)[:500]

    conn.execute(
        "INSERT INTO memories (session_id, timestamp, role, summary, detail, embedding, memory_type) "
        "VALUES (?, ?, 'system', ?, ?, '[]', 'compacted')",
        (session_id, time.time(), f"[consolidated {len(ids)} exchanges] {merged}",
         "\n".join(summaries)),
    )
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    conn.commit()
    logger.info("[MemoryDaemon] consolidated %d memories for session %s", len(ids), session_id[:8])
