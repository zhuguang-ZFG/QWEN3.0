"""Unit tests for device_gateway.motion dataclasses and helpers."""

from __future__ import annotations

import pytest

from device_gateway.motion import (
    MotionCommandKind,
    MotionEventKind,
    MotionPoint,
    MotionCommand,
    MotionEvent,
    home_command,
    move_to_command,
    pen_up_command,
    pen_down_command,
    stop_command,
    run_path_command,
)


class TestMotionPoint:
    def test_to_dict_defaults(self):
        p = MotionPoint(x=1.2346, y=2.3456)
        assert p.to_dict() == {"x": 1.235, "y": 2.346, "z": 0.0}

    def test_to_dict_with_z(self):
        p = MotionPoint(x=1.0, y=2.0, z=3.0)
        assert p.to_dict() == {"x": 1.0, "y": 2.0, "z": 3.0}


class TestMotionCommand:
    def test_home_to_dict(self):
        cmd = home_command()
        assert cmd.to_dict() == {"kind": "home", "feed": 900.0}

    def test_move_to_to_dict(self):
        cmd = move_to_command(10.0, 20.0, 5.0)
        assert cmd.to_dict() == {
            "kind": "move_to",
            "feed": 900.0,
            "target": {"x": 10.0, "y": 20.0, "z": 5.0},
        }

    def test_pen_up_to_dict(self):
        cmd = pen_up_command()
        assert cmd.to_dict() == {"kind": "pen_up", "feed": 900.0}

    def test_pen_down_to_dict(self):
        cmd = pen_down_command()
        assert cmd.to_dict() == {"kind": "pen_down", "feed": 900.0}

    def test_stop_to_dict(self):
        cmd = stop_command()
        assert cmd.to_dict() == {"kind": "stop", "feed": 900.0}

    def test_run_path_to_dict(self):
        path = [MotionPoint(0, 0), MotionPoint(1, 1)]
        cmd = run_path_command(path, feed=1200.0)
        data = cmd.to_dict()
        assert data["kind"] == "run_path"
        assert data["feed"] == 1200.0
        assert data["path"] == [{"x": 0.0, "y": 0.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 0.0}]
        assert cmd.path is not path  # should be a copy

    def test_command_id_in_to_dict(self):
        cmd = MotionCommand(kind=MotionCommandKind.HOME, command_id="c1")
        assert cmd.to_dict()["command_id"] == "c1"


class TestMotionEvent:
    def test_to_dict_minimal(self):
        evt = MotionEvent(kind=MotionEventKind.COMMAND_DONE, device_id="d1")
        assert evt.to_dict() == {"kind": "command_done", "device_id": "d1"}

    def test_to_dict_full(self):
        evt = MotionEvent(
            kind=MotionEventKind.POSITION,
            device_id="d1",
            position=MotionPoint(1.0, 2.0),
            command_id="c1",
            error="none",
            timestamp=1234567890.0,
        )
        data = evt.to_dict()
        assert data["kind"] == "position"
        assert data["device_id"] == "d1"
        assert data["position"] == {"x": 1.0, "y": 2.0, "z": 0.0}
        assert data["command_id"] == "c1"
        assert data["error"] == "none"
        assert data["timestamp"] == 1234567890.0

    def test_error_truncation(self):
        evt = MotionEvent(
            kind=MotionEventKind.ERROR,
            device_id="d1",
            error="x" * 300,
        )
        assert len(evt.to_dict()["error"]) == 200

    def test_enum_values(self):
        assert MotionCommandKind.HOME.value == "home"
        assert MotionEventKind.COMMAND_ACK.value == "command_ack"
