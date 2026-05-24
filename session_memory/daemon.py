"""Memory daemon — background inbox ingestion and periodic consolidation.

Runs as an asyncio background task, not in the request hot path.
Ingests files from data/memory_inbox/, extracts typed facts,
and periodically consolidates old memories into durable insights.
"""

import asyncio
import json
import os
import re
import time
import logging

from session_memory.store import save_typed_memory

logger = logging.getLogger(__name__)

DEFAULT_INBOX_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "memory_inbox"
)
CONSOLIDATION_THRESHOLD = 20

_running = False
_daemon_task: asyncio.Task | None = None
_stats = {
    "cycles": 0,
    "last_cycle_at": None,
    "last_ingested": 0,
    "last_consolidated": 0,
    "last_error": "",
}


def _inbox_dir() -> str:
    return os.environ.get("LIMA_MEMORY_INBOX", DEFAULT_INBOX_DIR)


def _interval_seconds() -> int:
    raw = os.environ.get("LIMA_MEMORY_CONSOLIDATION_INTERVAL", "300")
    try:
        return max(1, int(raw))
    except ValueError:
        return 300


async def start_daemon() -> dict:
    """Start the memory daemon as a background task."""
    global _running, _daemon_task
    if _running and _daemon_task and not _daemon_task.done():
        return {"started": False, **daemon_status()}
    _running = True
    logger.info(
        "[MemoryDaemon] started, inbox=%s, interval=%ds",
        _inbox_dir(),
        _interval_seconds(),
    )
    _daemon_task = asyncio.create_task(_daemon_loop())
    return {"started": True, **daemon_status()}


async def _daemon_loop() -> None:
    while _running:
        run_once()
        await asyncio.sleep(_interval_seconds())


async def stop_daemon() -> dict:
    global _running, _daemon_task
    _running = False
    task = _daemon_task
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _daemon_task = None
    return daemon_status()


def daemon_status() -> dict:
    task_alive = bool(_daemon_task and not _daemon_task.done())
    return {
        "running": _running,
        "task_alive": task_alive,
        "inbox_dir": _inbox_dir(),
        "interval_seconds": _interval_seconds(),
        **_stats,
    }


def run_once(*, ingest: bool = True, consolidate: bool = True) -> dict:
    """Run one daemon cycle outside the request path."""
    ingested = 0
    consolidated = 0
    error = ""
    try:
        if ingest:
            ingested = _ingest_inbox()
        if consolidate:
            consolidated = _consolidate_if_needed()
    except Exception as e:
        error = str(e)
        logger.warning("[MemoryDaemon] cycle error: %s", e)

    _stats.update({
        "cycles": int(_stats["cycles"]) + 1,
        "last_cycle_at": time.time(),
        "last_ingested": ingested,
        "last_consolidated": consolidated,
        "last_error": error,
    })
    return {
        "ingested": ingested,
        "consolidated": consolidated,
        "error": error,
        "status": daemon_status(),
    }


def _ingest_inbox(inbox_dir: str | None = None) -> int:
    """Scan inbox dir for .md/.json files, extract typed memories, archive processed."""
    inbox = inbox_dir or _inbox_dir()
    if not os.path.isdir(inbox):
        return 0

    ingested = 0
    for fname in os.listdir(inbox):
        fpath = os.path.join(inbox, fname)
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
                        text = item["summary"][:200]
                        if _sanitize_text(text) is None:
                            continue
                        facts.append((mt, text))
            elif isinstance(data, dict) and "summary" in data:
                mt = data.get("type", "project_fact")
                text = data["summary"][:200]
                if _sanitize_text(text) is not None:
                    facts.append((mt, text))
        except json.JSONDecodeError:
            pass
        return facts

    # Markdown/text: extract lines starting with "- " as facts
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("- ") and len(line) > 5:
            summary = line[2:].strip()[:200]
            if _sanitize_text(summary) is None:
                continue
            mem_type = _classify_line(summary)
            facts.append((mem_type, summary))
            if len(facts) >= 20:
                break

    return facts


_SECRET_PATTERNS = re.compile(
    r'(sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9\-]{20,}|'
    r'ghp_[a-zA-Z0-9]{36,}|xai-[a-zA-Z0-9]{20,}|'
    r'AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35}|'
    r'eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+|'
    r'Bearer\s+[a-zA-Z0-9._\-/+=]{20,}|'
    r'(?:key|token|secret|password|apikey|api_key)\s*[=:]\s*\S{16,})',
    re.IGNORECASE
)


def _sanitize_text(text: str) -> str | None:
    """Redact or reject text containing secrets."""
    if _SECRET_PATTERNS.search(text):
        logger.warning("[MemoryDaemon] secret pattern detected, skipping fact")
        return None
    return text


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


def _consolidate_if_needed() -> int:
    """Consolidate old memories when threshold is exceeded."""
    conn = None
    consolidated = 0
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
                if _consolidate_session(conn, sid):
                    consolidated += 1
    except Exception as e:
        logger.warning("[MemoryDaemon] consolidation error: %s", e)
    finally:
        if conn:
            conn.close()
    return consolidated


def _consolidate_session(conn, session_id: str) -> bool:
    """Merge oldest exchange memories into a single compacted entry."""
    oldest = conn.execute(
        "SELECT id, summary FROM memories "
        "WHERE session_id = ? AND memory_type = 'exchange' "
        "ORDER BY timestamp ASC LIMIT 10",
        (session_id,),
    ).fetchall()
    if len(oldest) < 5:
        return False

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
    return True
