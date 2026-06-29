"""In-memory device WebSocket session registry."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class DeviceSession:
    device_id: str
    websocket: Any
    fw_rev: str = ""
    capabilities: list[str] = field(default_factory=list)
    protocol_version: str = "lima-device-v1"
    negotiated_capabilities: frozenset[str] = field(default_factory=frozenset)
    attestation_action: str = ""
    last_uptime_ms: int = 0
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    inflight_tasks: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    inflight_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    connected_at: str = field(default_factory=_now_iso)

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
    # AUDIT-11-W1：最大并发设备连接数，防资源耗尽。
    # 同一 device_id 的新连接会覆盖旧的（不计入上限），故上限针对唯一设备数。
    _MAX_DEVICE_SESSIONS = 2000

    def __init__(self) -> None:
        self._sessions: dict[str, DeviceSession] = {}
        self._lock = threading.RLock()

    def register(self, session: DeviceSession) -> DeviceSession | None | str:
        """Register a session.

        Returns the previous session (if superseded), or the string "too_many"
        if the connection limit has been reached (caller should reject).
        """
        with self._lock:
            previous = self._sessions.get(session.device_id)
            # 新设备连接且已达上限 → 拒绝（已注册设备重连不算超限）
            if (
                previous is None
                and len(self._sessions) >= self._MAX_DEVICE_SESSIONS
            ):
                return "too_many"
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

    def active_device_ids(self) -> list[str]:
        """Return device_ids of all currently connected sessions (AUDIT-4-F2 reaper)."""
        with self._lock:
            return list(self._sessions.keys())

    def update_heartbeat(self, device_id: str, uptime_ms: int) -> None:
        with self._lock:
            session = self._sessions.get(device_id)
            if session:
                session.last_uptime_ms = uptime_ms

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


registry = SessionRegistry()
