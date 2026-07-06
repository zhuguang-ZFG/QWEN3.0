"""P2-a: idempotency key rollback on failed dispatch.

S10 幂等键"先占位后执行"存在缺陷：一旦 payload 构建或 dispatch 下发失败
（设备离线、路径生成异常等），幂等键已被消费，客户端用同一 Idempotency-Key
重试会被永久判为 duplicate，本应成功的命令永久丢失。

正确的幂等语义：失败可重试，只有成功才缓存。dispatch 失败/rejected 时必须
释放（DEL）刚占用的 key。

RED until _release_idempotency_key is wired into the dispatch endpoint.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from dlc_api import idempotency as _idem
from dlc_api import routes as _dlc_routes
from dlc_api.app import app
from dlc_api.deps import verify_dlc_api_token


def _override_token() -> str:
    return "dev-1"


app.dependency_overrides[verify_dlc_api_token] = _override_token


class _FakeRedis:
    """Minimal Redis supporting SET NX EX + DELETE for idempotency dedupe."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                removed += 1
        return removed


def _write_body() -> dict:
    return {"type": "write_text", "device_id": "dev-1", "payload": {"text": "你好"}}


def _install_fake_idem(monkeypatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr(_idem, "_idem_client", fake)
    monkeypatch.setattr(_idem, "_idem_prefix", "lima:dlc:idem")
    monkeypatch.setattr(_idem, "_idem_client_failed", False)
    return fake


def test_release_helper_exists() -> None:
    """_release_idempotency_key must exist as the rollback primitive."""
    assert hasattr(_dlc_routes, "_release_idempotency_key")


def test_failed_dispatch_releases_key_for_retry(monkeypatch) -> None:
    """dispatch_task 返回 failed → 幂等键必须被释放，同 key 重试不判 duplicate。"""
    fake = _install_fake_idem(monkeypatch)
    headers = {"Authorization": "Bearer t", "Idempotency-Key": "retry-1"}

    with patch("dlc_api.routes.check_key_limit", return_value=None):
        with patch("dlc_api.routes.handle_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = {
                "status": "success",
                "svg_path": "M0,0",
                "width": 10,
                "height": 10,
                "model": "deterministic",
                "error": None,
            }
            with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
                # First attempt: device offline → dispatch fails.
                mock_dispatch.return_value = {
                    "status": "failed",
                    "task_id": None,
                    "queue_depth": 0,
                    "error": "device offline",
                }
                client = TestClient(app)
                first = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)
                assert first.json()["status"] == "failed"
                # Key must have been released after the failure.
                assert not fake.store, f"idempotency key not released after failure: {fake.store}"

                # Second attempt with the SAME key: device back online → should succeed,
                # NOT be rejected as a duplicate.
                mock_dispatch.return_value = {
                    "status": "queued",
                    "task_id": "task-ok",
                    "queue_depth": 1,
                    "error": None,
                }
                second = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)
                assert second.json()["status"] == "queued", (
                    f"same key after failure must be retryable, got: {second.json()}"
                )
                assert mock_dispatch.await_count == 2


def test_successful_dispatch_keeps_key_locked(monkeypatch) -> None:
    """dispatch 成功 → 幂等键保留，同 key 重试仍判 duplicate（不回归去重语义）。"""
    _install_fake_idem(monkeypatch)
    headers = {"Authorization": "Bearer t", "Idempotency-Key": "keep-1"}

    with patch("dlc_api.routes.check_key_limit", return_value=None):
        with patch("dlc_api.routes.handle_write", new_callable=AsyncMock) as mock_write:
            mock_write.return_value = {
                "status": "success",
                "svg_path": "M0,0",
                "width": 10,
                "height": 10,
                "model": "deterministic",
                "error": None,
            }
            with patch("dlc_api.routes.dispatch_task", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = {
                    "status": "queued",
                    "task_id": "task-1",
                    "queue_depth": 1,
                    "error": None,
                }
                client = TestClient(app)
                first = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)
                second = client.post("/dlc/tasks/dispatch", json=_write_body(), headers=headers)

    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "duplicate"
    # Underlying dispatch ran only once.
    assert mock_dispatch.await_count == 1
