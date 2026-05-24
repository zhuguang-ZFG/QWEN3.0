"""Motion commands and events for LiMa Device Gateway.

Defines the bounded surface for writing-machine control. All motion commands
are synchronous instruction/ack flows. Motion events are asynchronous telemetry
from device to server.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MotionCommandKind(str, Enum):
    HOME = "home"
    MOVE_TO = "move_to"
    RUN_PATH = "run_path"
    PEN_UP = "pen_up"
    PEN_DOWN = "pen_down"
    STOP = "stop"


class MotionEventKind(str, Enum):
    POSITION = "position"
    COMMAND_ACK = "command_ack"
    COMMAND_DONE = "command_done"
    LIMIT_HIT = "limit_hit"
    ERROR = "error"


@dataclass
class MotionPoint:
    x: float
    y: float
    z: float = 0.0

    def to_dict(self) -> dict:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "z": round(self.z, 3)}


@dataclass
class MotionCommand:
    kind: MotionCommandKind
    target: MotionPoint | None = None
    path: list[MotionPoint] | None = None
    feed: float = 900.0
    command_id: str = ""

    def to_dict(self) -> dict:
        data: dict = {"kind": self.kind.value, "feed": self.feed}
        if self.target:
            data["target"] = self.target.to_dict()
        if self.path:
            data["path"] = [point.to_dict() for point in self.path]
        if self.command_id:
            data["command_id"] = self.command_id
        return data


@dataclass
class MotionEvent:
    kind: MotionEventKind
    device_id: str = ""
    position: MotionPoint | None = None
    command_id: str = ""
    error: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        data: dict = {"kind": self.kind.value, "device_id": self.device_id}
        if self.position:
            data["position"] = self.position.to_dict()
        if self.command_id:
            data["command_id"] = self.command_id
        if self.error:
            data["error"] = self.error[:200]
        if self.timestamp:
            data["timestamp"] = self.timestamp
        return data


def home_command() -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.HOME)


def move_to_command(x: float, y: float, z: float = 0.0) -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.MOVE_TO, target=MotionPoint(x, y, z))


def pen_up_command() -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.PEN_UP)


def pen_down_command() -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.PEN_DOWN)


def stop_command() -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.STOP)


def run_path_command(path: list[MotionPoint], feed: float = 900.0) -> MotionCommand:
    return MotionCommand(kind=MotionCommandKind.RUN_PATH, path=list(path), feed=feed)
