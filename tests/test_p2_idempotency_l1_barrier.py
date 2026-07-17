"""S10 idempotency L1 进程内二级屏障（参考业界 two-barrier 模式 + 复刻本仓库 rate_limiter L1+L2）。

缺口：idempotency 原本只有 Redis 单屏障。Redis 不可用时 fail-open 放行 =
**零去重保护**，同一 worker 内的重复 dispatch 会全部放过 → 物理设备重复画/写。

对照 rate_limiter.py：check_keyed_rate_limit 先查 Redis(L2)，Redis 不可用时
回退进程内内存滑窗(L1)。idempotency 缺这层 L1。

修复：补 L1 进程内 TTL 去重字典。Redis 可用时以 Redis 为权威(不碰 L1)；
Redis 不可用时用 L1 兜底(至少挡住同 worker 重复)。不翻转 fail-open——
L1 未命中仍放行(返回 True)，只是把"完全无去重"收窄成"挡住同 worker 重复"。

RED until claim/release_idempotency_key gain an L1 barrier.
"""

from __future__ import annotations

from dlc_api import idempotency as _idem


def _no_redis(monkeypatch) -> None:
    """强制 Redis 不可用（_get_idempotency_client 返回 None）；非生产 fail-open+L1。"""
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "dev")
    monkeypatch.setattr(_idem, "_get_idempotency_client", lambda: None)


def _reset_l1(monkeypatch) -> None:
    monkeypatch.setattr(_idem, "_l1_store", {})


def test_l1_blocks_same_worker_duplicate_when_redis_down(monkeypatch) -> None:
    """Redis 不可用时，同一 key claim 两次：第一次放行，第二次被 L1 拦截。"""
    _no_redis(monkeypatch)
    _reset_l1(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])

    assert _idem.claim_idempotency_key("dev-1:k1", "req-1") is True, "首次应放行"
    assert _idem.claim_idempotency_key("dev-1:k1", "req-2") is False, "同 worker 重复应被 L1 拦截"


def test_production_redis_down_raises_unavailable(monkeypatch) -> None:
    """生产 + Redis 不可用 → IdempotencyUnavailableError（fail-closed）。"""
    _no_redis(monkeypatch)
    monkeypatch.setenv("LIMA_RUNTIME_ENV", "production")
    _reset_l1(monkeypatch)
    try:
        _idem.claim_idempotency_key("dev-1:k-prod", "req-1")
        raise AssertionError("expected IdempotencyUnavailableError")
    except _idem.IdempotencyUnavailableError:
        pass


def test_l1_expires_after_ttl(monkeypatch) -> None:
    """L1 条目 TTL 过期后可重新 claim（不永久占用）。"""
    _no_redis(monkeypatch)
    _reset_l1(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])

    assert _idem.claim_idempotency_key("dev-1:k1", "req-1", ttl=600) is True
    clock[0] = 100.0 + 601  # 过期
    assert _idem.claim_idempotency_key("dev-1:k1", "req-2", ttl=600) is True, "TTL 过期后应可重新 claim"


def test_l1_release_matching_value_allows_reclaim(monkeypatch) -> None:
    """L1 release（value 匹配）后可重新 claim —— 失败重试语义。"""
    _no_redis(monkeypatch)
    _reset_l1(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])

    assert _idem.claim_idempotency_key("dev-1:k1", "req-1") is True
    _idem.release_idempotency_key("dev-1:k1", expected_value="req-1")
    assert _idem.claim_idempotency_key("dev-1:k1", "req-2") is True, "release 后应可重新 claim"


def test_l1_release_mismatched_value_keeps_key(monkeypatch) -> None:
    """L1 release（value 不匹配）绝不清除 —— 防误删他人 key（CAD 语义对齐 Redis 路径）。"""
    _no_redis(monkeypatch)
    _reset_l1(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])

    assert _idem.claim_idempotency_key("dev-1:k1", "req-2") is True
    # 迟到的 R1 用自己的 req-1 release → 不得删掉属于 R2 的 L1 条目。
    _idem.release_idempotency_key("dev-1:k1", expected_value="req-1")
    assert _idem.claim_idempotency_key("dev-1:k1", "req-3") is False, "value 不匹配却清除 = 误删他人 key"


def test_redis_available_keeps_l1_recovery_barrier(monkeypatch) -> None:
    """Redis 可用时也写 L1，避免故障恢复窗口绕过先前的 L1 claim。"""
    _reset_l1(monkeypatch)

    class _FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, str] = {}

        def set(self, key, value, *, nx=False, ex=None):
            if nx and key in self.store:
                return None
            self.store[key] = value
            return True

    fake = _FakeRedis()
    monkeypatch.setattr(_idem, "_get_idempotency_client", lambda: (fake, "lima:dlc:idem"))

    assert _idem.claim_idempotency_key("dev-1:k1", "req-1") is True
    assert "dev-1:k1" in _idem._l1_store


def test_redis_recovery_does_not_bypass_existing_l1_claim(monkeypatch) -> None:
    _reset_l1(monkeypatch)
    monkeypatch.setattr(_idem, "_get_idempotency_client", lambda: None)
    assert _idem.claim_idempotency_key("dev-1:k1", "req-1") is True

    class _RecoveredRedis:
        def set(self, *_args, **_kwargs):
            return True

    monkeypatch.setattr(_idem, "_get_idempotency_client", lambda: (_RecoveredRedis(), "idem"))
    assert _idem.claim_idempotency_key("dev-1:k1", "req-2") is False


def test_l1_sweep_caps_unbounded_growth(monkeypatch) -> None:
    """成功 dispatch 的 idem_key 不重复 → L1 无界增长；惰性清扫须把条目数压在上限附近。"""
    _no_redis(monkeypatch)
    _reset_l1(monkeypatch)
    clock = [100.0]
    monkeypatch.setattr(_idem.time, "monotonic", lambda: clock[0])
    cap = _idem._L1_MAX_ENTRIES

    # 灌入远超上限的未过期条目（模拟高吞吐长跑）
    for i in range(cap * 3):
        _idem.claim_idempotency_key(f"dev-1:k{i}", f"req-{i}")

    assert len(_idem._l1_store) <= cap, f"L1 不得无界增长: {len(_idem._l1_store)} > {cap}"
