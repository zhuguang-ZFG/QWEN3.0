"""P2 自审修复：release_idempotency_key 必须 compare-and-delete，防误删他人 key。

缺陷链（无 expected_value 校验时）：
1. R1 claim(value=req1)，dispatch 极慢
2. TTL 到期 key 消失
3. R2（同 Idempotency-Key）claim(value=req2) 成功执行，key 现属 R2
4. R1 失败 → 无条件 DEL → 误删 R2 的 key
5. R3（同 key）claim 成功 → 重复执行 R2 已完成的任务 → 物理设备画/写两遍

修复：release 只在 GET key == 本请求 request_id 时才 DEL（CAD）。

RED until release_idempotency_key gains an expected_value CAD guard.
"""

from __future__ import annotations

from dlc_api import idempotency as _idem


class _FakeRedis:
    """Minimal Redis: SET NX EX + GET + DELETE."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, *keys):
        removed = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                removed += 1
        return removed


def _install(monkeypatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr(_idem, "_idem_client", fake)
    monkeypatch.setattr(_idem, "_idem_prefix", "lima:dlc:idem")
    monkeypatch.setattr(_idem, "_idem_client_failed", False)
    return fake


def test_release_matching_value_deletes(monkeypatch) -> None:
    """release 传入与 claim 相同的 value → 正常删除。"""
    fake = _install(monkeypatch)
    _idem.claim_idempotency_key("dev-1:k1", "req-1")
    assert fake.store == {"lima:dlc:idem:dev-1:k1": "req-1"}
    _idem.release_idempotency_key("dev-1:k1", expected_value="req-1")
    assert fake.store == {}, "匹配 value 应被删除"


def test_release_mismatched_value_keeps_key(monkeypatch) -> None:
    """release 传入与当前 value 不同的 request_id → 绝不删除（防误删他人 key）。"""
    fake = _install(monkeypatch)
    # 模拟 R2 已重新占用同一 key（value=req-2）。
    _idem.claim_idempotency_key("dev-1:k1", "req-2")
    # R1 迟到的 release 用自己的 req-1 → 不得删掉属于 R2 的 key。
    _idem.release_idempotency_key("dev-1:k1", expected_value="req-1")
    assert fake.store == {"lima:dlc:idem:dev-1:k1": "req-2"}, "value 不匹配却删除 = 误删他人 key"
