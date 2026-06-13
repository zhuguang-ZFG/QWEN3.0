"""Tests for device memory store isolation and controls."""
import time
from device_memory.store import MemoryStore
from device_memory.schemas import MemoryEntry, MemoryType


def test_create_and_recall_memory():
    """Memory can be created and recalled."""
    store = MemoryStore()
    entry = MemoryEntry(
        id="mem_001",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="favorite_color",
        value="blue",
        ttl_days=30,
        created_at=int(time.time()),
        source="user_explicit",
    )
    store.create(entry)
    recalled = store.recall("dev_a", "favorite_color")
    assert recalled is not None
    assert recalled.value == "blue"


def test_recall_respects_ttl():
    """Expired memories are not recalled."""
    store = MemoryStore()
    now = int(time.time())
    entry = MemoryEntry(
        id="mem_002",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="old_pref",
        value="data",
        ttl_days=1,
        created_at=now - 86400 * 2,  # 2 days ago
        source="inferred",
    )
    store.create(entry)
    recalled = store.recall("dev_a", "old_pref")
    assert recalled is None


def test_recall_ignores_disabled():
    """Disabled memories are not recalled."""
    store = MemoryStore()
    entry = MemoryEntry(
        id="mem_003",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="pref_disabled",
        value="data",
        ttl_days=30,
        created_at=int(time.time()),
        source="inferred",
    )
    store.create(entry)
    store.disable("mem_003")
    recalled = store.recall("dev_a", "pref_disabled")
    assert recalled is None


def test_cross_family_isolation():
    """Memories are isolated by device_id."""
    store = MemoryStore()
    entry_a = MemoryEntry(
        id="mem_a",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="shared_key",
        value="value_a",
        ttl_days=30,
        created_at=int(time.time()),
        source="user",
    )
    entry_b = MemoryEntry(
        id="mem_b",
        device_id="dev_b",
        type=MemoryType.PREFERENCE,
        key="shared_key",
        value="value_b",
        ttl_days=30,
        created_at=int(time.time()),
        source="user",
    )
    store.create(entry_a)
    store.create(entry_b)

    recalled_a = store.recall("dev_a", "shared_key")
    recalled_b = store.recall("dev_b", "shared_key")

    assert recalled_a.value == "value_a"
    assert recalled_b.value == "value_b"


def test_delete_memory():
    """Parent can delete a memory."""
    store = MemoryStore()
    entry = MemoryEntry(
        id="mem_del",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="to_delete",
        value="data",
        ttl_days=30,
        created_at=int(time.time()),
        source="inferred",
    )
    store.create(entry)
    assert store.delete("mem_del") is True
    assert store.recall("dev_a", "to_delete") is None


def test_export_device_memories():
    """Parent can export all device memories."""
    store = MemoryStore()
    entry = MemoryEntry(
        id="mem_exp",
        device_id="dev_a",
        type=MemoryType.PREFERENCE,
        key="export_key",
        value="export_val",
        ttl_days=30,
        created_at=int(time.time()),
        source="user",
    )
    store.create(entry)
    exported = store.export("dev_a")
    assert "export_key" in exported
    assert "export_val" in exported


def test_reset_device_memories():
    """Parent can reset all device memories."""
    store = MemoryStore()
    for i in range(3):
        entry = MemoryEntry(
            id=f"mem_{i}",
            device_id="dev_reset",
            type=MemoryType.PREFERENCE,
            key=f"key_{i}",
            value=f"val_{i}",
            ttl_days=30,
            created_at=int(time.time()),
            source="user",
        )
        store.create(entry)

    count = store.reset("dev_reset")
    assert count == 3
    assert len(store.list_by_device("dev_reset")) == 0
