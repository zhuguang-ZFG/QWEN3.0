"""C1 Phase 1: ledger 生产启用测试（backend 选择 + 跨进程可见性）。"""

from __future__ import annotations

import os
import uuid

import pytest

from device_ledger import store as ledger_store_mod
from device_ledger.events import new_event
from device_ledger.redis_store import RedisLedgerStore


def _require_real_redis() -> str:
    """Return a live Redis URL, or skip the test with a clear reason."""
    url = (os.environ.get("LIMA_TEST_REDIS_URL") or os.environ.get("LIMA_DEVICE_REDIS_URL") or "").strip()
    if not url:
        pytest.skip("Redis 跨进程测试需要真实 Redis：请设置 LIMA_TEST_REDIS_URL 或 LIMA_DEVICE_REDIS_URL")
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        client.close()
    except Exception as exc:
        pytest.skip(f"Redis 不可用（{url}）：{type(exc).__name__}: {exc}")
    return url


def test_configure_ledger_store_from_env_selects_redis_backend(monkeypatch):
    original = ledger_store_mod.ledger_manager.store
    monkeypatch.setenv("LIMA_DEVICE_LEDGER_STORE", "redis")
    # RedisLedgerStore 的连接是惰性的，URL 无需指向真实 Redis 即可验证后端选择。
    monkeypatch.setattr("config.db_config.DEVICE_REDIS_URL", "redis://127.0.0.1:6399/9")
    try:
        ledger_store_mod.configure_ledger_store_from_env()
        assert ledger_store_mod.ledger_store.backend_name == "redis"
        assert ledger_store_mod.ledger_store.shared_across_processes is True
    finally:
        ledger_store_mod.set_ledger_store_for_tests(original)


def test_configure_ledger_store_from_env_defaults_to_memory(monkeypatch):
    original = ledger_store_mod.ledger_manager.store
    monkeypatch.delenv("LIMA_DEVICE_LEDGER_STORE", raising=False)
    monkeypatch.setattr("config.db_config.DEVICE_REDIS_URL", "")
    try:
        ledger_store_mod.configure_ledger_store_from_env()
        assert ledger_store_mod.ledger_store.backend_name == "memory"
    finally:
        ledger_store_mod.set_ledger_store_for_tests(original)


def test_redis_ledger_event_visible_to_second_store_instance():
    """跨进程持久化：一个 store 实例写入的事件，另一个实例（模拟新进程）可读。"""
    url = _require_real_redis()
    prefix = f"test:ledger:xproc:{uuid.uuid4().hex}"
    writer = RedisLedgerStore(url, key_prefix=prefix)
    try:
        event = new_event(
            event_type="task_created",
            task_id="task-xproc-1",
            device_id="dev-xproc",
            payload={"task": {"task_id": "task-xproc-1"}, "status": "created"},
        )
        writer.append_event(event)

        reader = RedisLedgerStore(url, key_prefix=prefix)
        try:
            events = reader.events_for_task("task-xproc-1")
            assert [e.event_id for e in events] == [event.event_id]
            replay = reader.replay_task("task-xproc-1")
            assert replay["status"] == "created"
            assert replay["event_count"] == 1
        finally:
            reader.close()
    finally:
        writer.reset()
        writer.close()
