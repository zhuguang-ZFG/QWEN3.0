"""Tests for ESP32S bridge integration."""

import pytest

from esp32s_adapter.bridge import ESP32SBridge


class TestESP32SBridge:
    @pytest.mark.asyncio
    async def test_connect_device(self):
        bridge = ESP32SBridge()
        hello = await bridge.connect_device("dev_b01")
        assert hello["type"] == "hello"
        assert hello["protocol"] == "lima-device-v1"
        assert hello["device_id"] == "dev_b01"
        assert "home" in hello["capabilities"]
        assert "run_path" in hello["capabilities"]

    @pytest.mark.asyncio
    async def test_disconnect_device(self):
        bridge = ESP32SBridge()
        await bridge.connect_device("dev_b02")
        assert "dev_b02" in bridge.list_connected_devices()

        await bridge.disconnect_device("dev_b02")
        assert "dev_b02" not in bridge.list_connected_devices()

    @pytest.mark.asyncio
    async def test_dispatch_task_home(self):
        bridge = ESP32SBridge()
        await bridge.connect_device("dev_b03")

        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_b03",
            "task_id": "tb1",
            "capability": "home",
            "params": {},
        }
        edge_c_task = await bridge.dispatch_task(lima_task)
        assert edge_c_task["type"] == "motion_task"
        assert edge_c_task["capability"] == "home"
        assert edge_c_task["source"] == "client"
        assert "route_policy" in edge_c_task

    @pytest.mark.asyncio
    async def test_dispatch_to_disconnected_device(self):
        bridge = ESP32SBridge()
        lima_task = {
            "type": "task_dispatch",
            "device_id": "dev_none",
            "task_id": "tb2",
            "capability": "home",
            "params": {},
        }
        with pytest.raises(ValueError, match="not connected"):
            await bridge.dispatch_task(lima_task)

    @pytest.mark.asyncio
    async def test_recv_event_from_device(self):
        bridge = ESP32SBridge()
        await bridge.connect_device("dev_b04")

        edge_c_event = {
            "session_id": "sess_test",
            "type": "motion_event",
            "task_id": "tb3",
            "phase": "done",
            "device_id": "dev_b04",
        }
        await bridge.inject_device_event("dev_b04", edge_c_event)

        lima_event = await bridge.recv_event("dev_b04", timeout=1.0)
        assert lima_event["type"] == "motion_event"
        assert lima_event["task_id"] == "tb3"
        assert lima_event["phase"] == "done"
        assert "session_id" not in lima_event

    @pytest.mark.asyncio
    async def test_list_connected_devices(self):
        bridge = ESP32SBridge()
        await bridge.connect_device("dev_b11")
        await bridge.connect_device("dev_b12")
        await bridge.connect_device("dev_b13")

        devices = bridge.list_connected_devices()
        assert len(devices) == 3
        assert "dev_b11" in devices
        assert "dev_b12" in devices
        assert "dev_b13" in devices


class TestFakeDeviceRoundtrip:
    @pytest.mark.asyncio
    async def test_home_task_full_lifecycle(self):
        bridge = ESP32SBridge()
        device_id = "dev_rt01"

        # 1. 设备连接
        hello = await bridge.connect_device(device_id)
        assert hello["device_id"] == device_id

        # 2. 下发 home 任务
        lima_task = {
            "type": "task_dispatch",
            "device_id": device_id,
            "task_id": "rt_task_1",
            "capability": "home",
            "params": {},
        }
        edge_c_task = await bridge.dispatch_task(lima_task)
        assert edge_c_task["task_id"] == "rt_task_1"

        # 3. 模拟设备回传 accepted 事件
        await bridge.inject_device_event(
            device_id,
            {
                "session_id": "sess_rt",
                "type": "motion_event",
                "task_id": "rt_task_1",
                "phase": "accepted",
                "device_id": device_id,
            },
        )
        event_accepted = await bridge.recv_event(device_id, timeout=1.0)
        assert event_accepted["phase"] == "accepted"

        # 4. 模拟设备回传 running 事件
        await bridge.inject_device_event(
            device_id,
            {
                "session_id": "sess_rt",
                "type": "motion_event",
                "task_id": "rt_task_1",
                "phase": "running",
                "device_id": device_id,
            },
        )
        event_running = await bridge.recv_event(device_id, timeout=1.0)
        assert event_running["phase"] == "running"

        # 5. 模拟设备回传 done 事件
        await bridge.inject_device_event(
            device_id,
            {
                "session_id": "sess_rt",
                "type": "motion_event",
                "task_id": "rt_task_1",
                "phase": "done",
                "device_id": device_id,
            },
        )
        event_done = await bridge.recv_event(device_id, timeout=1.0)
        assert event_done["phase"] == "done"
        assert event_done["task_id"] == "rt_task_1"

    @pytest.mark.asyncio
    async def test_run_path_with_progress(self):
        bridge = ESP32SBridge()
        device_id = "dev_rt02"

        await bridge.connect_device(device_id)

        lima_task = {
            "type": "task_dispatch",
            "device_id": device_id,
            "task_id": "rt_task_2",
            "capability": "run_path",
            "params": {"path": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 10, "z": 0}], "feed": 500.0},
        }
        await bridge.dispatch_task(lima_task)

        # 模拟进度事件
        await bridge.inject_device_event(
            device_id,
            {
                "session_id": "sess_rt2",
                "type": "motion_event",
                "task_id": "rt_task_2",
                "phase": "progress",
                "device_id": device_id,
                "progress": {"done_segments": 1, "total_segments": 2, "percent": 50},
            },
        )
        event_progress = await bridge.recv_event(device_id, timeout=1.0)
        assert event_progress["phase"] == "progress"
        assert event_progress["progress"]["percent"] == 50
