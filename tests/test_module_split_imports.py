"""Import-compat smoke after large-file splits (CQ-087)."""

import backend_utils
import backends_registry
from session_memory.store import MEMORY_TYPES, MemoryEntry


def test_backends_canonical_exports():
    assert "scnet_ds_flash" in backends_registry.BACKENDS
    assert backend_utils.detect_vendor("https://api.groq.com/openai/v1")


def test_session_memory_store_facade():
    assert "exchange" in MEMORY_TYPES
    assert MemoryEntry
