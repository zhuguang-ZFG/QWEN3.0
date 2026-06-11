"""Test device_route_memory module."""

from device_gateway.device_route_memory import (
    record_route_decision,
    get_route_memory,
    reset_route_memory_for_tests,
)


def test_record_first_decision() -> None:
    """Record first decision, verify preferred_backends and counts."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "backend_a", True)

    memory = get_route_memory("device_001")
    assert memory["device_id"] == "device_001"
    assert memory["preferred_backends"] == ["backend_a"]
    assert memory["success_count"] == 1
    assert memory["total_count"] == 1
    assert "last_route_timestamp" in memory
    assert memory["last_route_timestamp"].endswith("Z")


def test_record_multiple_decisions() -> None:
    """Multiple decisions for same device, check backend ordering (most recent first)."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "backend_a", True)
    record_route_decision("device_001", "backend_b", False)
    record_route_decision("device_001", "backend_c", True)

    memory = get_route_memory("device_001")
    assert memory["preferred_backends"] == ["backend_c", "backend_b", "backend_a"]


def test_record_max_backends() -> None:
    """Verify preferred_backends capped at 10 entries."""
    reset_route_memory_for_tests()

    for i in range(15):
        record_route_decision("device_001", f"backend_{i}", True)

    memory = get_route_memory("device_001")
    assert len(memory["preferred_backends"]) == 10
    assert memory["preferred_backends"][0] == "backend_14"


def test_get_route_memory_empty() -> None:
    """Get memory for unknown device returns empty dict."""
    reset_route_memory_for_tests()

    memory = get_route_memory("unknown_device")
    assert memory == {}


def test_get_route_memory_filled() -> None:
    """Get memory after recording, verify all fields."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "backend_a", True)

    memory = get_route_memory("device_001")
    assert memory["device_id"] == "device_001"
    assert memory["preferred_backends"] == ["backend_a"]
    assert memory["success_count"] == 1
    assert memory["total_count"] == 1


def test_reset_memory() -> None:
    """Reset clears all records."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "backend_a", True)
    memory = get_route_memory("device_001")
    assert memory["device_id"] == "device_001"
    assert memory["preferred_backends"] == ["backend_a"]
    assert memory["success_count"] == 1
    assert memory["total_count"] == 1
    assert "last_route_timestamp" in memory
    assert memory["last_route_timestamp"].endswith("Z")

    reset_route_memory_for_tests()
    assert get_route_memory("device_001") == {}


def test_empty_device_id() -> None:
    """Record with empty device_id is silently skipped."""
    reset_route_memory_for_tests()

    record_route_decision("", "backend_a", True)

    memory = get_route_memory("device_001")
    assert memory == {}


def test_empty_backend() -> None:
    """Record with empty backend is silently skipped."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "", True)

    memory = get_route_memory("device_001")
    assert memory == {}


def test_success_count_tracking() -> None:
    """Verify success_count and total_count increment correctly across multiple records."""
    reset_route_memory_for_tests()

    record_route_decision("device_001", "backend_a", True)
    record_route_decision("device_001", "backend_b", False)
    record_route_decision("device_001", "backend_c", True)

    memory = get_route_memory("device_001")
    assert memory["success_count"] == 2
    assert memory["total_count"] == 3
