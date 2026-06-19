"""Bridge conversion from LiMa motion_task payloads to Edge-D command sequences."""

from __future__ import annotations

from fake_u1_helpers import motion_task_to_u1_commands


def test_cloud_task_command_translation_matches_u1_protocol() -> None:
    """The bridge converts LiMa motion_task payloads into valid Edge-D command sequences."""
    commands = motion_task_to_u1_commands(
        {
            "device_id": "dev-1",
            "task_id": "task-path",
            "capability": "run_path",
            "params": {
                "feed": 900,
                "path": [
                    {"cmd": "M", "x": 0, "y": 0, "z": 0},
                    {"cmd": "L", "x": 10, "y": 0, "z": 0},
                ],
            },
        }
    )
    assert [cmd["cmd"] for cmd in commands] == ["PATH_BEGIN", "PATH_SEG", "PATH_SEG", "PATH_END"]
    assert commands[0]["total_segments"] == 2
