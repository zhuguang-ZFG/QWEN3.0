"""In-memory device WebSocket session registry."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceSession:
    device_id: str
    websocket: Any
    fw_rev: str = ""
    capabilities: list[str] = field(default_factory=list)
    last_uptime_ms: int = 0
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    inflight_tasks: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    inflight_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    async def send_json(self, payload: dict[str, Any]) -> None:
        async with self.send_lock:
            await self.websocket.send_json(payload)

    def mark_task_dispatched(self, task: dict[str, Any]) -> None:
        with self.inflight_lock:
            self.inflight_tasks[task["task_id"]] = task

    def mark_task_acknowledged(self, task_id: str) -> None:
        with self.inflight_lock:
            self.inflight_tasks.pop(task_id, None)

    def outstanding_tasks(self) -> list[dict[str, Any]]:
        with self.inflight_lock:
            return list(self.inflight_tasks.values())

    def take_outstanding_tasks(self) -> list[dict[str, Any]]:
        with self.inflight_lock:
            tasks = list(self.inflight_tasks.values())
            self.inflight_tasks.clear()
            return tasks


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, DeviceSession] = {}
        self._lock = threading.RLock()

    def register(self, session: DeviceSession) -> DeviceSession | None:
        with self._lock:
            previous = self._sessions.get(session.device_id)
            self._sessions[session.device_id] = session
            return previous

    def unregister(self, device_id: str, websocket: Any | None = None) -> None:
        with self._lock:
            current = self._sessions.get(device_id)
            if current is None:
                return
            if websocket is not None and current.websocket is not websocket:
                return
            self._sessions.pop(device_id, None)

    def get(self, device_id: str) -> DeviceSession | None:
        with self._lock:
            return self._sessions.get(device_id)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def update_heartbeat(self, device_id: str, uptime_ms: int) -> None:
        with self._lock:
            session = self._sessions.get(device_id)
            if session:
                session.last_uptime_ms = uptime_ms

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


registry = SessionRegistry()
