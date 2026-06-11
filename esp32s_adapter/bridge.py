"""Bridge between LiMa device_gateway and ESP32S_XYZ adapter."""

from __future__ import annotations

import asyncio
from typing import Any

from .protocol import edge_c_to_lima_event, lima_to_edge_c_task
from .session import SessionManager


class ESP32SBridge:
    """Bridges LiMa device_gateway to ESP32S_XYZ devices."""

    def __init__(self):
        self.session_manager = SessionManager()
        self._running = False

    async def connect_device(self, device_id: str) -> dict[str, Any]:
        """Register a new device connection.

        Returns:
            hello message for LiMa device_gateway
        """
        session = self.session_manager.create_session(device_id)
        return {
            "type": "hello",
            "protocol": "lima-device-v1",
            "device_id": device_id,
            "capabilities": ["home", "run_path", "get_device_info", "pause", "resume", "stop"],
            "fw_rev": "esp32s-v1.0",
            "model": "esp32s-xyz",
        }

    async def disconnect_device(self, device_id: str) -> None:
        """Remove device session."""
        self.session_manager.remove_session(device_id)

    async def dispatch_task(self, lima_task: dict[str, Any]) -> dict[str, Any]:
        """Dispatch LiMa task to ESP32S device.

        Args:
            lima_task: LiMa task_dispatch frame

        Returns:
            Edge-C motion_task that was sent
        """
        device_id = lima_task["device_id"]
        session = self.session_manager.get_session(device_id)
        if session is None:
            raise ValueError(f"device {device_id} not connected")

        edge_c_task = lima_to_edge_c_task(lima_task)
        await session.send_task(edge_c_task)
        return edge_c_task

    async def recv_event(self, device_id: str, timeout: float = 5.0) -> dict[str, Any]:
        """Receive motion_event from device and convert to LiMa format.

        Args:
            device_id: Device to receive from
            timeout: Timeout in seconds

        Returns:
            LiMa motion_event frame
        """
        session = self.session_manager.get_session(device_id)
        if session is None:
            raise ValueError(f"device {device_id} not connected")

        edge_c_event = await session.recv_event(timeout=timeout)
        return edge_c_to_lima_event(edge_c_event)

    async def inject_device_event(self, device_id: str, edge_c_event: dict[str, Any]) -> None:
        """Inject event from device (used by fake device in tests)."""
        session = self.session_manager.get_session(device_id)
        if session is None:
            raise ValueError(f"device {device_id} not connected")
        await session.inject_event(edge_c_event)

    def list_connected_devices(self) -> list[str]:
        """List all connected device IDs."""
        return self.session_manager.list_active_devices()
