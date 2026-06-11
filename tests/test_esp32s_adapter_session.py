"""Tests for ESP32S_XYZ session management."""

import asyncio

import pytest

from esp32s_adapter.session import ESP32SSession, SessionManager


class TestESP32SSession:
    @pytest.mark.asyncio
    async def test_session_creation(self):
        session = ESP32SSession("dev_001")
        assert session.device_id == "dev_001"
        assert session.session_id.startswith("lima-esp32s-dev_001-")
        assert session.connected_at > 0

    @pytest.mark.asyncio
    async def test_send_and_recv_task(self):
        session = ESP32SSession("dev_002")
        task = {"type": "motion_task", "task_id": "t1"}

        await session.send_task(task)
        assert session.has_pending_tasks()

    @pytest.mark.asyncio
    async def test_inject_and_recv_event(self):
        session = ESP32SSession("dev_003")
        event = {"type": "motion_event", "task_id": "t1", "phase": "running"}

        await session.inject_event(event)
        assert session.has_pending_events()

        received = await session.recv_event(timeout=1.0)
        assert received["task_id"] == "t1"
        assert received["phase"] == "running"

    @pytest.mark.asyncio
    async def test_recv_event_timeout(self):
        session = ESP32SSession("dev_004")
        with pytest.raises(asyncio.TimeoutError):
            await session.recv_event(timeout=0.1)


class TestSessionManager:
    def test_create_session(self):
        manager = SessionManager()
        session = manager.create_session("dev_101")
        assert session.device_id == "dev_101"
        assert "dev_101" in manager.list_active_devices()

    def test_get_existing_session(self):
        manager = SessionManager()
        session1 = manager.create_session("dev_102")
        session2 = manager.get_session("dev_102")
        assert session1 is session2

    def test_get_nonexistent_session(self):
        manager = SessionManager()
        session = manager.get_session("dev_999")
        assert session is None

    def test_remove_session(self):
        manager = SessionManager()
        manager.create_session("dev_103")
        assert "dev_103" in manager.list_active_devices()

        manager.remove_session("dev_103")
        assert "dev_103" not in manager.list_active_devices()

    def test_list_active_devices(self):
        manager = SessionManager()
        manager.create_session("dev_201")
        manager.create_session("dev_202")
        manager.create_session("dev_203")

        devices = manager.list_active_devices()
        assert len(devices) == 3
        assert "dev_201" in devices
        assert "dev_202" in devices
        assert "dev_203" in devices

    def test_create_session_idempotent(self):
        manager = SessionManager()
        session1 = manager.create_session("dev_301")
        session2 = manager.create_session("dev_301")
        assert session1 is session2
        assert len(manager.list_active_devices()) == 1
