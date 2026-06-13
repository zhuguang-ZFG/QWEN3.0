"""Import-compat smoke after large-file splits (CQ-087)."""

import pytest


def test_backends_canonical_exports():
    import backend_utils
    import backends_registry

    assert "scnet_ds_flash" in backends_registry.BACKENDS
    assert backend_utils.detect_vendor("https://api.groq.com/openai/v1")


@pytest.mark.skip(reason="Skip: routes.agent_tasks not yet implemented")
def test_agent_tasks_compat_symbols():
    from routes import agent_tasks

    assert agent_tasks._store is not None
    assert agent_tasks.TaskCreateBody is not None
    assert callable(agent_tasks._create_task_from_body)
    assert callable(agent_tasks._reset_for_tests)


def test_session_memory_store_facade():
    from session_memory.store import (
        MEMORY_TYPES,
        MemoryEntry,
    )

    assert "exchange" in MEMORY_TYPES
    assert MemoryEntry


@pytest.mark.skip(reason="Skip: agent_runtime.orchestrator not yet implemented")
def test_orchestrator_facade():
    from agent_runtime.orchestrator import (
        AgentRunQueue,
        AgentRunRequest,
        QueueStatus,
        WorkerGovernor,
    )

    assert QueueStatus.PENDING.value == "pending"
    q = AgentRunQueue()
    assert q.stats()["total"] == 0
    assert WorkerGovernor(q).stats()["total"] == 0
    assert AgentRunRequest(goal="test").goal == "test"
