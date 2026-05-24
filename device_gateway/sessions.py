"""In-memory device WebSocket session registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceSession:
    device_id: str
    websocket: Any
    fw_rev: str = ""
    capabilities: list[str] = field(default_factory=list)
    last_uptime_ms: int = 0


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, DeviceSession] = {}

    def register(self, session: DeviceSession) -> DeviceSession | None:
        previous = self._sessions.get(session.device_id)
        self._sessions[session.device_id] = session
        return previous

    def unregister(self, device_id: str, websocket: Any | None = None) -> None:
        current = self._sessions.get(device_id)
        if current is None:
            return
        if websocket is not None and current.websocket is not websocket:
            return
        self._sessions.pop(device_id, None)

    def get(self, device_id: str) -> DeviceSession | None:
        return self._sessions.get(device_id)

    def count(self) -> int:
        return len(self._sessions)

    def clear(self) -> None:
        self._sessions.clear()


registry = SessionRegistry()

