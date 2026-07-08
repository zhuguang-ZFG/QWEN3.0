"""Deterministic virtual device for LiMa Device Gateway testing.

The fake device simulates a bounded writing machine. It never talks to real
hardware and exists to exercise motion protocol behavior before a physical
transport is wired.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field

from device_gateway.path_data import (
    MotionCommand,
    MotionCommandKind,
    MotionEvent,
    MotionEventKind,
    MotionPoint,
)
from device_gateway.safety import DEFAULT_WORKSPACE_MM, MAX_FEED, MAX_POINTS


@dataclass
class FakeDeviceState:
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    position: MotionPoint = field(default_factory=lambda: MotionPoint(0, 0, 10))
    pen_down: bool = False
    is_homed: bool = False
    stopped: bool = False
    last_command_id: str = ""
    event_log: list[MotionEvent] = field(default_factory=list)
    error_count: int = 0


class FakeDevice:
    """A deterministic virtual writing machine for tests."""

    def __init__(self, device_id: str = "") -> None:
        self._state = FakeDeviceState(device_id=device_id or uuid.uuid4().hex[:8])

    @property
    def device_id(self) -> str:
        return self._state.device_id

    @property
    def position(self) -> MotionPoint:
        return self._state.position

    @property
    def event_log(self) -> list[MotionEvent]:
        return list(self._state.event_log)

    def handle_command(self, cmd: MotionCommand) -> list[MotionEvent]:
        self._state.last_command_id = cmd.command_id
        events: list[MotionEvent] = [self._event(MotionEventKind.COMMAND_ACK, cmd)]

        if cmd.kind == MotionCommandKind.HOME:
            events.extend(self._do_home(cmd))
        elif cmd.kind == MotionCommandKind.MOVE_TO:
            events.extend(self._do_move_to(cmd))
        elif cmd.kind == MotionCommandKind.PEN_UP:
            events.extend(self._do_pen_up(cmd))
        elif cmd.kind == MotionCommandKind.PEN_DOWN:
            events.extend(self._do_pen_down(cmd))
        elif cmd.kind == MotionCommandKind.STOP:
            events.extend(self._do_stop(cmd))
        elif cmd.kind == MotionCommandKind.RUN_PATH:
            events.extend(self._do_run_path(cmd))
        else:
            events.append(self._error(cmd, f"unknown command: {cmd.kind}"))

        self._state.event_log.extend(events)
        return events

    def _event(
        self,
        kind: MotionEventKind,
        cmd: MotionCommand,
        *,
        position: MotionPoint | None = None,
        error: str = "",
    ) -> MotionEvent:
        return MotionEvent(
            kind=kind,
            device_id=self.device_id,
            position=position,
            command_id=cmd.command_id,
            error=error,
            timestamp=time.time(),
        )

    def _do_home(self, cmd: MotionCommand) -> list[MotionEvent]:
        self._state.is_homed = True
        self._state.stopped = False
        self._state.pen_down = False
        self._state.position = MotionPoint(0, 0, 10)
        return [
            self._event(MotionEventKind.POSITION, cmd, position=self._state.position),
            self._event(MotionEventKind.COMMAND_DONE, cmd),
        ]

    def _do_move_to(self, cmd: MotionCommand) -> list[MotionEvent]:
        if not cmd.target:
            return [self._error(cmd, "no target for move_to")]
        if not self._state.is_homed:
            return [self._error(cmd, "not homed")]

        point, limit_hit = self._clamp_point(cmd.target)
        self._state.position = point
        events: list[MotionEvent] = []
        if limit_hit:
            events.append(self._event(MotionEventKind.LIMIT_HIT, cmd, position=point))
        events.extend(
            [
                self._event(MotionEventKind.POSITION, cmd, position=point),
                self._event(MotionEventKind.COMMAND_DONE, cmd),
            ]
        )
        return events

    def _do_pen_up(self, cmd: MotionCommand) -> list[MotionEvent]:
        if not self._state.is_homed:
            return [self._error(cmd, "not homed")]
        self._state.pen_down = False
        return [self._event(MotionEventKind.COMMAND_DONE, cmd)]

    def _do_pen_down(self, cmd: MotionCommand) -> list[MotionEvent]:
        if not self._state.is_homed:
            return [self._error(cmd, "not homed")]
        self._state.pen_down = True
        return [self._event(MotionEventKind.COMMAND_DONE, cmd)]

    def _do_stop(self, cmd: MotionCommand) -> list[MotionEvent]:
        self._state.pen_down = False
        self._state.stopped = True
        return [self._event(MotionEventKind.COMMAND_DONE, cmd)]

    def _do_run_path(self, cmd: MotionCommand) -> list[MotionEvent]:
        if not cmd.path:
            return [self._error(cmd, "no path for run_path")]
        if len(cmd.path) > MAX_POINTS:
            return [self._error(cmd, "path has too many points")]
        if not self._valid_feed(cmd.feed):
            return [self._error(cmd, "feed is outside allowed range")]
        if not self._state.is_homed:
            return [self._error(cmd, "not homed")]

        events: list[MotionEvent] = []
        for raw_point in cmd.path:
            point, limit_hit = self._clamp_point(raw_point)
            self._state.position = point
            if limit_hit:
                events.append(self._event(MotionEventKind.LIMIT_HIT, cmd, position=point))
            events.append(self._event(MotionEventKind.POSITION, cmd, position=point))
        events.append(self._event(MotionEventKind.COMMAND_DONE, cmd))
        return events

    def _clamp_point(self, point: MotionPoint) -> tuple[MotionPoint, bool]:
        x = self._clamp_axis(point.x, "x")
        y = self._clamp_axis(point.y, "y")
        z = self._clamp_axis(point.z, "z")
        clamped = MotionPoint(x, y, z)
        return clamped, clamped != point

    def _clamp_axis(self, value: float, axis: str) -> float:
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return 0.0
        return max(0.0, min(float(value), DEFAULT_WORKSPACE_MM[axis]))

    def _valid_feed(self, feed: float) -> bool:
        return isinstance(feed, (int, float)) and math.isfinite(feed) and 0 < feed <= MAX_FEED

    def _error(self, cmd: MotionCommand, msg: str) -> MotionEvent:
        self._state.error_count += 1
        return self._event(MotionEventKind.ERROR, cmd, error=msg)

    def reset(self) -> None:
        self._state = FakeDeviceState(device_id=self._state.device_id)
