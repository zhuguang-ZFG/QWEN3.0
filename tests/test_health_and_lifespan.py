"""最小测试：优雅关停 + /health 深度检查。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _mock_session(device_id: str, *, fail_close: bool = False) -> MagicMock:
    s = MagicMock()
    s.device_id = device_id
    s.websocket = MagicMock()
    if fail_close:
        s.websocket.close = AsyncMock(side_effect=RuntimeError("connection lost"))
    else:
        s.websocket.close = AsyncMock()
    return s


def _run_lifespan(sessions: list[MagicMock], *, backend_name: str = "memory") -> MagicMock:
    """在 patch 后的 registry/task_store 下跑一次完整 lifespan，返回 mock_store。"""
    mock_reg = MagicMock()
    mock_reg.active_sessions.return_value = sessions
    mock_store = MagicMock()
    mock_store.backend_name = backend_name

    from server_dlc import app

    with (
        patch("device_gateway.sessions.registry", mock_reg),
        patch("device_gateway.store.task_store", mock_store),
        patch("device_gateway.store.configure_task_store_from_env") as mock_configure,
    ):
        with TestClient(app):
            pass  # 触发 lifespan startup + shutdown
        mock_configure.assert_called_once()
    return mock_store


# ---------------------------------------------------------------------------
# 优雅关停（lifespan shutdown）测试
# ---------------------------------------------------------------------------


class TestLifespanStartup:
    """验证 lifespan startup 配置 task store（fail-fast）。"""

    def test_configure_task_store_called_on_startup(self) -> None:
        _run_lifespan([])

    def test_configure_failure_prevents_startup(self) -> None:
        from server_dlc import app

        with patch(
            "device_gateway.store.configure_task_store_from_env",
            side_effect=RuntimeError("redis misconfigured"),
        ):
            try:
                with TestClient(app):
                    pass
            except RuntimeError as exc:
                assert "redis misconfigured" in str(exc)
            else:
                raise AssertionError("expected configure failure to abort startup")


class TestLifespanShutdown:
    """验证 lifespan 退出时关闭会话 + Redis 连接。"""

    def test_closes_all_sessions(self) -> None:
        """lifespan 退出时关闭所有活跃 WebSocket 会话。"""
        s1 = _mock_session("dev-a")
        s2 = _mock_session("dev-b")

        _run_lifespan([s1, s2])

        s1.websocket.close.assert_awaited_once_with(code=1012, reason="server_restart")
        s2.websocket.close.assert_awaited_once_with(code=1012, reason="server_restart")

    def test_single_close_failure_does_not_block_others(self) -> None:
        """单个会话 close 异常不影响其余会话关闭。"""
        s_ok = _mock_session("dev-ok")
        s_fail = _mock_session("dev-fail", fail_close=True)
        s_late = _mock_session("dev-late")

        _run_lifespan([s_ok, s_fail, s_late])

        s_ok.websocket.close.assert_awaited_once()
        s_fail.websocket.close.assert_awaited_once()  # 被调用了，只是抛异常
        s_late.websocket.close.assert_awaited_once()

    def test_redis_connection_closed_when_backend_is_redis(self) -> None:
        """当 task_store 后端为 redis 时，关闭 Redis 连接池。"""
        mock_store = _run_lifespan([], backend_name="redis")

        mock_store._redis.close.assert_called_once()

    def test_redis_not_closed_when_backend_is_memory(self) -> None:
        """当 task_store 后端为 memory 时，不调用 Redis 关闭。"""
        mock_store = _run_lifespan([], backend_name="memory")

        assert not mock_store._redis.close.called


# ---------------------------------------------------------------------------
# /health 深度检查测试
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """验证 /health 端点包含 Redis 依赖状态。"""

    def test_memory_backend_returns_200(self) -> None:
        """memory 后端返回 200 + dependencies 字段。"""
        from dlc_api.app import app

        with patch(
            "dlc_api.routes.task_store_health",
            return_value={"backend": "memory", "shared_across_processes": False},
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "dlc-drawing"
        assert data["version"] == "0.4.0-p3"
        assert data["dependencies"]["task_store"] == "memory"

    def test_redis_ok_returns_200(self) -> None:
        """Redis 可用时返回 200 + dependencies。"""
        mock_store = MagicMock()
        mock_store._redis.ping.return_value = True

        from dlc_api.app import app

        with (
            patch(
                "dlc_api.routes.task_store_health",
                return_value={"backend": "redis", "shared_across_processes": True},
            ),
            patch("device_gateway.store.task_store", mock_store),
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dependencies"]["task_store"] == "redis"

    def test_redis_unavailable_returns_503(self) -> None:
        """Redis 不可用时返回 503 degraded。"""
        mock_store = MagicMock()
        mock_store._redis.ping.side_effect = ConnectionError("redis down")

        from dlc_api.app import app

        with (
            patch(
                "dlc_api.routes.task_store_health",
                return_value={"backend": "redis", "shared_across_processes": True},
            ),
            patch("device_gateway.store.task_store", mock_store),
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["task_store"] == "redis"
        # 原有字段仍存在
        assert data["service"] == "dlc-drawing"
        assert data["version"] == "0.4.0-p3"

    def test_env_expects_redis_but_backend_is_memory_returns_503(self) -> None:
        """env 配置了 Redis URL 但实际 backend 为 memory → 503 degraded。"""
        from dlc_api.app import app

        mock_redis = MagicMock()
        mock_redis.device_redis_url = "redis://localhost:6379"

        with (
            patch(
                "dlc_api.routes.task_store_health",
                return_value={"backend": "memory", "shared_across_processes": False},
            ),
            patch("dlc_api.routes.REDIS", mock_redis),
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["task_store"] == "memory"

    def test_no_redis_url_and_memory_backend_returns_200(self) -> None:
        """纯 memory 部署（无 Redis URL）→ 200 ok。"""
        from dlc_api.app import app

        mock_redis = MagicMock()
        mock_redis.device_redis_url = ""

        with (
            patch(
                "dlc_api.routes.task_store_health",
                return_value={"backend": "memory", "shared_across_processes": False},
            ),
            patch("dlc_api.routes.REDIS", mock_redis),
            patch.dict("os.environ", {"LIMA_DEVICE_TASK_STORE": ""}, clear=False),
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_task_store_pref_redis_with_memory_backend_returns_503(self) -> None:
        """LIMA_DEVICE_TASK_STORE=redis 但 backend 仍是 memory → 503。"""
        from dlc_api.app import app

        mock_redis = MagicMock()
        mock_redis.device_redis_url = ""

        with (
            patch(
                "dlc_api.routes.task_store_health",
                return_value={"backend": "memory", "shared_across_processes": False},
            ),
            patch("dlc_api.routes.REDIS", mock_redis),
            patch.dict("os.environ", {"LIMA_DEVICE_TASK_STORE": "redis"}, clear=False),
        ):
            client = TestClient(app)
            resp = client.get("/health")

        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"
