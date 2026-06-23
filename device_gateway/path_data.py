"""Shared path data: stroke font, workspace limits, clamping, and motion types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# ── Stroke font: 5x9 monospace glyphs for ASCII 0x20–0x7E ──────────────────
# Each glyph is a list of (x, y) segments: even indices are pen-up moves,
# odd indices are pen-down line-to. Coordinates are in a 5-wide, 9-tall cell.
# Z is the pen-up sentinel (None means pen-up to start of next segment).

_FONT_GLYPHS: dict[str, list[tuple[Any, ...]]] = {
    " ": [(None, 0, 0), (None, 5, 0)],
    "A": [(None, 0, 9), (0, 5), (5, 9), (None, 1, 5), (4, 5)],
    "B": [(None, 0, 0), (0, 9), (5, 8), (5, 4), (0, 4), (None, 0, 4), (5, 0)],
    "C": [(None, 5, 8), (0, 8), (0, 0), (5, 0)],
    "D": [(None, 0, 0), (0, 9), (5, 8), (5, 0), (0, 0)],
    "E": [(None, 5, 9), (0, 9), (0, 4), (3, 4), (None, 0, 4), (0, 0), (5, 0)],
    "F": [(None, 5, 9), (0, 9), (0, 4), (3, 4), (None, 0, 4), (0, 0)],
    "G": [(None, 5, 8), (0, 8), (0, 0), (5, 0), (5, 4), (2, 4)],
    "H": [(None, 0, 0), (0, 9), (None, 5, 9), (5, 0), (None, 0, 5), (5, 5)],
    "I": [(None, 0, 9), (5, 9), (None, 2.5, 9), (2.5, 0), (None, 0, 0), (5, 0)],
    "J": [(None, 5, 9), (5, 5), (5, 0), (0, 0)],
    "K": [(None, 0, 0), (0, 9), (None, 0, 5), (5, 9), (None, 2, 5), (5, 0)],
    "L": [(None, 0, 9), (0, 0), (5, 0)],
    "M": [(None, 0, 0), (0, 9), (2.5, 4), (5, 9), (5, 0)],
    "N": [(None, 0, 0), (0, 9), (5, 0), (5, 9)],
    "O": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8)],
    "P": [(None, 0, 0), (0, 9), (5, 9), (5, 5), (0, 5)],
    "Q": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8), (None, 3, 4), (5, 1)],
    "R": [(None, 0, 0), (0, 9), (5, 9), (5, 5), (0, 5), (None, 2, 5), (5, 0)],
    "S": [(None, 5, 9), (0, 8), (0, 5), (5, 4), (5, 0), (0, 0)],
    "T": [(None, 0, 9), (5, 9), (None, 2.5, 9), (2.5, 0)],
    "U": [(None, 0, 9), (0, 0), (5, 0), (5, 9)],
    "V": [(None, 0, 9), (2.5, 0), (5, 9)],
    "W": [(None, 0, 9), (1.25, 0), (2.5, 4), (3.75, 0), (5, 9)],
    "X": [(None, 0, 9), (5, 0), (None, 0, 0), (5, 9)],
    "Y": [(None, 0, 9), (2.5, 5), (5, 9), (None, 2.5, 5), (2.5, 0)],
    "Z": [(None, 0, 9), (5, 9), (0, 0), (5, 0)],
    "0": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8)],
    "1": [(None, 2, 9), (2.5, 9), (2.5, 0), (0, 0)],
    "2": [(None, 0, 8), (5, 8), (5, 4), (0, 4), (0, 0), (5, 0)],
    "3": [(None, 0, 9), (5, 9), (5, 5), (0, 5), (None, 5, 5), (5, 0), (0, 0)],
    "4": [(None, 0, 9), (0, 4), (5, 4), (None, 3, 9), (3, 0)],
    "5": [(None, 5, 9), (0, 9), (0, 4), (5, 4), (5, 0), (0, 0)],
    "6": [(None, 5, 9), (0, 9), (0, 0), (5, 0), (5, 4), (0, 4)],
    "7": [(None, 0, 9), (5, 9), (3, 0)],
    "8": [(None, 0, 8), (0, 0), (5, 0), (5, 8), (0, 8), (None, 0, 4), (5, 4)],
    "9": [(None, 5, 0), (5, 8), (0, 8), (0, 4), (5, 4)],
    ".": [(None, 2, 0), (3, 0)],
    ",": [(None, 3, 0), (2, -2)],
    "!": [(None, 2.5, 9), (2.5, 3), (None, 2.5, 0), (2.5, 0)],
    "?": [(None, 0, 8), (3, 9), (5, 7), (4, 5), (2.5, 4), (None, 2.5, 2), (2.5, 0)],
    "-": [(None, 1, 5), (4, 5)],
    "_": [(None, 0, 0), (5, 0)],
    "+": [(None, 2.5, 8), (2.5, 1), (None, 0, 4.5), (5, 4.5)],
    "=": [(None, 0, 3), (5, 3), (None, 0, 6), (5, 6)],
    "/": [(None, 5, 9), (0, 0)],
    "\\": [(None, 0, 9), (5, 0)],
    "(": [(None, 4, 10), (2, 7), (2, 2), (4, -1)],
    ")": [(None, 1, 10), (3, 7), (3, 2), (1, -1)],
    "[": [(None, 4, 10), (1, 10), (1, -1), (4, -1)],
    "]": [(None, 1, 10), (4, 10), (4, -1), (1, -1)],
    "<": [(None, 5, 9), (0, 5), (5, 0)],
    ">": [(None, 0, 9), (5, 5), (0, 0)],
    ":": [(None, 2.5, 7), (2.5, 7), (None, 2.5, 2), (2.5, 2)],
    ";": [(None, 2.5, 7), (2.5, 7), (None, 3, 2), (2, 0)],
    "'": [(None, 2.5, 9), (2.5, 6)],
    '"': [(None, 1.5, 9), (1.5, 6), (None, 3.5, 9), (3.5, 6)],
    "#": [(None, 1, 9), (1, 0), (None, 4, 9), (4, 0), (None, 0, 3), (5, 3), (None, 0, 6), (5, 6)],
    "$": [(None, 4, 10), (1, 8), (0, 5), (5, 4), (4, 0), (1, -1), (None, 2.5, 10), (2.5, -1)],
    "%": [(None, 5, 9), (0, 0), (None, 1, 9), (1, 6), (4, 6), (4, 9), (1, 9), (None, 1, 3), (4, 3), (4, 0), (1, 0)],
    "&": [(None, 5, 8), (0, 6), (0, 5), (2, 5), (0, 2), (0, 0), (5, 0), (5, 5)],
    "@": [(None, 3, 4), (1, 4), (1, 7), (2, 8), (4, 8), (5, 6), (5, 2), (4, 0), (2, 0), (1, 2), (1, 4)],
    "*": [(None, 2.5, 9), (2.5, 0), (None, 0, 6), (5, 3), (None, 0, 3), (5, 6)],
    "|": [(None, 2.5, 9), (2.5, 0)],
    "~": [(None, 0, 6), (1.5, 8), (3.5, 6), (5, 8)],
    "`": [(None, 2.5, 9), (2.5, 7)],
    "^": [(None, 0, 7), (2.5, 9), (5, 7)],
    "{": [(None, 4, 10), (2.5, 7), (1, 5), (2.5, 3), (1, 1), (2.5, -1)],
    "}": [(None, 1, 10), (2.5, 7), (4, 5), (2.5, 3), (4, 1), (2.5, -1)],
}

FONT_CHAR_W = 6.0
FONT_CHAR_H = 11.0
FONT_BASELINE = 2.0

# ── Safety limits ────────────────────────────────────────────────────────────

MAX_PATH_POINTS = 200
MAX_WORKSPACE_MM = 200.0
MIN_WORKSPACE_MM = 1.0


def clamp_path(
    path: list[dict[str, float]],
    max_points: int = MAX_PATH_POINTS,
) -> list[dict[str, float]]:
    """Clamp a path to workspace bounds and maximum point count."""
    result: list[dict[str, float]] = []
    for pt in path[:max_points]:
        x = max(-MAX_WORKSPACE_MM, min(MAX_WORKSPACE_MM, pt["x"]))
        y = max(-MAX_WORKSPACE_MM, min(MAX_WORKSPACE_MM, pt["y"]))
        result.append({"x": round(x, 2), "y": round(y, 2), "z": round(pt.get("z", 0), 2)})
    return result


# ── Motion commands and events ───────────────────────────────────────────────


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
