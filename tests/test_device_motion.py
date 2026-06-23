"""Tests for M12 motion commands, fake device, and safety constraints."""

import math

import pytest

from device_gateway.fake_device import FakeDevice, FakeDeviceState
from device_gateway.path_data import (
    MotionCommandKind,
    MotionEvent,
    MotionEventKind,
    MotionPoint,
    home_command,
    move_to_command,
    pen_down_command,
    pen_up_command,
    run_path_command,
    stop_command,
)
from device_gateway.safety import DEFAULT_WORKSPACE_MM, MAX_POINTS, SafetyError, safe_point


def _event_kinds(events):
    return [event.kind for event in events]


def test_motion_point_to_dict():
    point = MotionPoint(10.5, 20.25, 0.0)

    assert point.to_dict() == {"x": 10.5, "y": 20.25, "z": 0.0}


def test_home_command():
    command = home_command()

    assert command.kind == MotionCommandKind.HOME
    assert command.to_dict()["kind"] == "home"


def test_move_to_command():
    command = move_to_command(30.0, 40.0)

    assert command.kind == MotionCommandKind.MOVE_TO
    assert command.target.x == 30.0
    assert command.target.y == 40.0


def test_pen_commands():
    assert pen_up_command().kind == MotionCommandKind.PEN_UP
    assert pen_down_command().kind == MotionCommandKind.PEN_DOWN


def test_stop_command():
    assert stop_command().kind == MotionCommandKind.STOP


def test_run_path_command_copies_path_list():
    path = [MotionPoint(0, 0), MotionPoint(50, 50)]
    command = run_path_command(path, feed=800)
    path.append(MotionPoint(99, 99))

    assert command.kind == MotionCommandKind.RUN_PATH
    assert len(command.path) == 2
    assert command.feed == 800


def test_command_to_dict():
    command = move_to_command(10, 20, 5)

    assert command.to_dict() == {
        "kind": "move_to",
        "feed": 900.0,
        "target": {"x": 10.0, "y": 20.0, "z": 5.0},
    }


def test_motion_event_to_dict():
    event = MotionEvent(
        kind=MotionEventKind.POSITION,
        device_id="dev1",
        position=MotionPoint(1, 2),
        command_id="c1",
        timestamp=123.0,
    )

    assert event.to_dict() == {
        "kind": "position",
        "device_id": "dev1",
        "position": {"x": 1.0, "y": 2.0, "z": 0.0},
        "command_id": "c1",
        "timestamp": 123.0,
    }


def test_error_event_dict_truncates_long_error():
    event = MotionEvent(kind=MotionEventKind.ERROR, error="x" * 250)

    assert len(event.to_dict()["error"]) == 200


def test_fake_device_home_emits_ack_position_done():
    device = FakeDevice()
    events = device.handle_command(home_command())

    assert device.position.x == 0
    assert device.position.y == 0
    assert _event_kinds(events) == [
        MotionEventKind.COMMAND_ACK,
        MotionEventKind.POSITION,
        MotionEventKind.COMMAND_DONE,
    ]


def test_fake_device_move_to():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(move_to_command(50, 60))

    assert device.position.x == 50
    assert device.position.y == 60
    assert _event_kinds(events) == [
        MotionEventKind.COMMAND_ACK,
        MotionEventKind.POSITION,
        MotionEventKind.COMMAND_DONE,
    ]


def test_fake_device_move_to_clamps_workspace_and_reports_limit():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(move_to_command(9999, -50, 999))

    assert device.position.x == DEFAULT_WORKSPACE_MM["x"]
    assert device.position.y == 0
    assert device.position.z == DEFAULT_WORKSPACE_MM["z"]
    assert MotionEventKind.LIMIT_HIT in _event_kinds(events)


def test_fake_device_nonfinite_target_reports_limit_and_clamps_to_zero():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(move_to_command(math.nan, math.inf, -math.inf))

    assert device.position.to_dict() == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert MotionEventKind.LIMIT_HIT in _event_kinds(events)


def test_fake_device_pen_state_requires_home():
    device = FakeDevice()
    events = device.handle_command(pen_down_command())

    assert device._state.pen_down is False
    assert _event_kinds(events) == [MotionEventKind.COMMAND_ACK, MotionEventKind.ERROR]


def test_fake_device_pen_state_after_home():
    device = FakeDevice()
    device.handle_command(home_command())
    device.handle_command(pen_down_command())
    assert device._state.pen_down is True

    device.handle_command(pen_up_command())
    assert device._state.pen_down is False


def test_fake_device_rejects_move_before_home():
    device = FakeDevice()
    events = device.handle_command(move_to_command(10, 10))

    assert _event_kinds(events) == [MotionEventKind.COMMAND_ACK, MotionEventKind.ERROR]


def test_fake_device_run_path_reports_positions_and_done():
    device = FakeDevice()
    device.handle_command(home_command())
    device.handle_command(pen_down_command())
    path = [MotionPoint(10, 10), MotionPoint(20, 20), MotionPoint(30, 30)]
    events = device.handle_command(run_path_command(path))

    assert device.position.x == 30
    assert device.position.y == 30
    assert _event_kinds(events) == [
        MotionEventKind.COMMAND_ACK,
        MotionEventKind.POSITION,
        MotionEventKind.POSITION,
        MotionEventKind.POSITION,
        MotionEventKind.COMMAND_DONE,
    ]


def test_fake_device_run_path_clamps_each_axis_and_reports_limit():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(run_path_command([MotionPoint(-1, 101, 99)]))

    assert device.position.to_dict() == {"x": 0.0, "y": 100.0, "z": 20.0}
    assert MotionEventKind.LIMIT_HIT in _event_kinds(events)


def test_fake_device_run_path_rejects_bad_feed():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(run_path_command([MotionPoint(1, 1)], feed=0))

    assert _event_kinds(events) == [MotionEventKind.COMMAND_ACK, MotionEventKind.ERROR]
    assert "feed" in events[-1].error


def test_fake_device_run_path_rejects_too_many_points():
    device = FakeDevice()
    device.handle_command(home_command())
    events = device.handle_command(run_path_command([MotionPoint(1, 1)] * (MAX_POINTS + 1)))

    assert _event_kinds(events) == [MotionEventKind.COMMAND_ACK, MotionEventKind.ERROR]
    assert "too many" in events[-1].error


def test_fake_device_stop_raises_pen_and_marks_stopped():
    device = FakeDevice()
    device.handle_command(home_command())
    device.handle_command(pen_down_command())
    events = device.handle_command(stop_command())

    assert device._state.pen_down is False
    assert device._state.stopped is True
    assert _event_kinds(events) == [MotionEventKind.COMMAND_ACK, MotionEventKind.COMMAND_DONE]


def test_fake_device_event_log():
    device = FakeDevice()
    device.handle_command(home_command())
    device.handle_command(move_to_command(10, 10))

    assert len(device.event_log) == 6


def test_fake_device_reset():
    device = FakeDevice()
    device.handle_command(home_command())
    device.reset()

    assert device.position.x == 0
    assert device._state.is_homed is False
    assert len(device.event_log) == 0


def test_safe_point_valid():
    point = safe_point(50, 50, 5)

    assert point["x"] == 50.0


def test_safe_point_outside_raises():
    with pytest.raises(SafetyError):
        safe_point(9999, 0, 0)
    with pytest.raises(SafetyError):
        safe_point(-1, 0, 0)
    with pytest.raises(SafetyError):
        safe_point(0, 0, 9999)


def test_default_workspace_bounds():
    assert DEFAULT_WORKSPACE_MM["x"] == 100.0
    assert DEFAULT_WORKSPACE_MM["y"] == 100.0
    assert DEFAULT_WORKSPACE_MM["z"] == 20.0


def test_fake_device_state_defaults():
    state = FakeDeviceState()

    assert len(state.device_id) == 8
    assert state.is_homed is False
    assert state.pen_down is False
    assert state.stopped is False
