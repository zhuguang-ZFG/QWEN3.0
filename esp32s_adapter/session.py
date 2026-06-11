"""WebSocket session management for ESP32S_XYZ devices."""

from __future__ import annotations

import asyncio
import time
from typing import Any


class ESP32SSession:
    """Manages a single ESP32S_XYZ device WebSocket session."""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.session_id = f"lima-esp32s-{device_id}-{int(time.time() * 1000)}"
        self.connected_at = time.time()
        self._tx_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._rx_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def send_task(self, edge_c_task: dict[str, Any]) -> None:
        """Queue a motion_task for transmission to device."""
        await self._tx_queue.put(edge_c_task)

    async def recv_event(self, timeout: float = 5.0) -> dict[str, Any]:
        """Wait for next motion_event from device."""
        return await asyncio.wait_for(self._rx_queue.get(), timeout=timeout)

    async def inject_event(self, edge_c_event: dict[str, Any]) -> None:
        """Inject motion_event from device (used by adapter)."""
        await self._rx_queue.put(edge_c_event)

    def has_pending_tasks(self) -> bool:
        """Check if there are tasks waiting to be sent."""
        return not self._tx_queue.empty()

    def has_pending_events(self) -> bool:
        """Check if there are events waiting to be read."""
        return not self._rx_queue.empty()


class SessionManager:
    """Manages multiple device sessions."""

    def __init__(self):
        self._sessions: dict[str, ESP32SSession] = {}

    def create_session(self, device_id: str) -> ESP32SSession:
        """Create or return existing session for device."""
        if device_id in self._sessions:
            return self._sessions[device_id]
        session = ESP32SSession(device_id)
        self._sessions[device_id] = session
        return session

    def get_session(self, device_id: str) -> ESP32SSession | None:
        """Get existing session or None."""
        return self._sessions.get(device_id)

    def remove_session(self, device_id: str) -> None:
        """Remove session on disconnect."""
        self._sessions.pop(device_id, None)

    def list_active_devices(self) -> list[str]:
        """List all connected device IDs."""
        return list(self._sessions.keys())
