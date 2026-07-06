"""S10 idempotency Redis 粘滞重连修复（Cursor 复审发现）。

缺陷：_get_idempotency_client 首次连接失败置 _idem_client_failed=True 后
永久粘滞返回 None，即使 Redis 恢复也不重连，直到进程重启 —— 去重永久失效，
fail-open 下物理设备可能重复画/写。

修复：失败后进入基于时间的冷却窗口（_IDEM_RETRY_COOLDOWN 秒），窗口内继续
放行不重试（避免每次 dispatch 卡在 Redis 连接超时上），窗口过后允许重连一次，
使 Redis 短暂抖动恢复后能自愈。不改变 fail-open 语义（Redis 挂时仍放行）。

RED until _get_idempotency_client gains cooldown-based retry.
"""

from __future__ import annotations

import device_gateway.redis_store_helpers as _helpers
from dlc_api import idempotency as _idem


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True


def _reset(monkeypatch) -> None:
    monkeypatch.setattr(_idem, "_idem_client", None)
    monkeypatch.setattr(_idem, "_idem_prefix", "")
    monkeypatch.setattr(_idem, "_idem_client_failed", False)
    monkeypatch.setattr(_idem, "_idem_client_failed_at", 0.0)


def test_reconnects_after_cooldown(monkeypatch) -> None:
    """Redis 首次失败后，冷却窗口过后应重连成功（不永久粘滞）。"""
    _reset(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])

    calls = {"n": 0}
    fake = _FakeRedis()

    def _connect(url, name, *, key_prefix):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("redis down")
        return fake, key_prefix

    monkeypatch.setattr(_helpers, "connect_redis", _connect)

    # T=100：首次连接失败 → 放行（None）
    assert _idem._get_idempotency_client() is None
    assert calls["n"] == 1

    # T=105（冷却窗口内）：不重试，继续放行
    clock[0] = 105.0
    assert _idem._get_idempotency_client() is None
    assert calls["n"] == 1, "冷却窗口内不应重连（保留超时保护）"

    # T=140（超过冷却窗口）：允许重连一次，成功
    clock[0] = 140.0
    result = _idem._get_idempotency_client()
    assert result is not None, "冷却后 Redis 恢复应重连自愈"
    assert result[0] is fake
    assert calls["n"] == 2


def test_success_caches_client(monkeypatch) -> None:
    """首次连接成功后应缓存 client，后续调用不再重连。"""
    _reset(monkeypatch)
    calls = {"n": 0}
    fake = _FakeRedis()

    def _connect(url, name, *, key_prefix):
        calls["n"] += 1
        return fake, key_prefix

    monkeypatch.setattr(_helpers, "connect_redis", _connect)

    r1 = _idem._get_idempotency_client()
    r2 = _idem._get_idempotency_client()
    assert r1 == r2
    assert r1[0] is fake
    assert calls["n"] == 1, "成功后应缓存，不重复连接"
