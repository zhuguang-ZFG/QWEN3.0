import os
import tempfile

os.environ["LIMA_SESSION_DB"] = tempfile.mktemp(suffix=".db")
os.environ["LIMA_SESSION_MEMORY"] = "1"
os.environ["LIMA_LESSONS_DIR"] = tempfile.mkdtemp()

from session_memory.compactor import (
    COMPACTION_THRESHOLD,
    compact_session,
    needs_compaction,
)
from session_memory.store import count_memories, save_memory


def test_needs_compaction_false_below_threshold():
    sid = "compact-test-1"
    for i in range(5):
        save_memory(sid, "exchange", f"memory {i}")
    assert needs_compaction(sid) is False


def test_needs_compaction_true_above_threshold():
    sid = "compact-test-2"
    for i in range(COMPACTION_THRESHOLD + 5):
        save_memory(sid, "exchange", f"memory {i}")
    assert needs_compaction(sid) is True


def test_compact_session_reduces_count():
    sid = "compact-test-3"
    for i in range(25):
        save_memory(sid, "exchange", f"entry {i}")

    before = count_memories(sid)
    result = compact_session(sid)

    assert result["compacted"] is True
    assert result["before"] == before
    assert result["after"] < before
    assert result["compressed_count"] == 10


def test_compact_session_preserves_summary():
    sid = "compact-test-4"
    for i in range(25):
        save_memory(sid, "exchange", f"topic_{i}")

    compact_session(sid)
    from session_memory.store import get_recent_memories
    memories = get_recent_memories(sid, limit=50)
    compacted = [m for m in memories if m.role == "compacted"]
    assert len(compacted) >= 1
    assert "压缩摘要" in compacted[0].summary


def test_compact_session_below_threshold_skips():
    sid = "compact-test-5"
    for i in range(5):
        save_memory(sid, "exchange", f"small {i}")
    result = compact_session(sid)
    assert result["compacted"] is False


def test_custom_summarizer():
    sid = "compact-test-6"
    for i in range(25):
        save_memory(sid, "exchange", f"item {i}")

    def my_summarizer(summaries):
        return f"CUSTOM: {len(summaries)} items compressed"

    result = compact_session(sid, summarizer=my_summarizer)
    assert result["compacted"] is True

    from session_memory.store import get_recent_memories
    memories = get_recent_memories(sid, limit=50)
    compacted = [m for m in memories if m.role == "compacted"]
    assert "CUSTOM" in compacted[0].summary
