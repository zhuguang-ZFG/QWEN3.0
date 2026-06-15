"""M6: Tests for device memory extractor (task episode + failure pattern extraction)."""

from __future__ import annotations

import json
import time

import pytest

from device_ledger.events import new_event
from device_memory.extractor import extract_episode_from_terminal, extract_device_failure_from_event
from device_memory.schemas import MemoryType


class TestExtractEpisodeFromTerminal:
    def test_done_terminal_creates_episode(self):
        event = new_event(
            event_type="task_terminal",
            task_id="task-ep-001",
            device_id="dev-1",
            payload={
                "terminal_event": {
                    "phase": "done",
                    "capability": "write_text",
                    "params": {"text": "hello", "feed": 800},
                }
            },
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-ep-001")
        assert entry is not None
        assert entry.type == MemoryType.TASK_EPISODE
        data = json.loads(entry.value)
        assert data["outcome"] == "success"
        assert data["task_type"] == "creative"

    def test_failed_terminal_creates_episode_with_error(self):
        event = new_event(
            event_type="task_terminal",
            task_id="task-ep-fail",
            device_id="dev-1",
            payload={
                "terminal_event": {
                    "phase": "failed",
                    "capability": "run_path",
                    "error": {"code": "E_MISSING_PATH", "reason": "missing"},
                    "params": {},
                }
            },
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-ep-fail")
        assert entry is not None
        data = json.loads(entry.value)
        assert data["outcome"] == "failure"
        assert entry.confidence == 0.3
        assert data["task_type"] == "path_render"

    def test_cancelled_terminal_creates_episode(self):
        event = new_event(
            event_type="task_terminal",
            task_id="task-ep-cancel",
            device_id="dev-1",
            payload={
                "terminal_event": {
                    "phase": "cancelled",
                    "capability": "draw_generated",
                    "params": {"prompt": "cat"},
                }
            },
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-ep-cancel")
        assert entry is not None
        data = json.loads(entry.value)
        assert data["outcome"] == "cancelled"

    def test_non_terminal_returns_none(self):
        event = new_event(
            event_type="motion_event",
            task_id="task-run",
            device_id="dev-1",
            payload={"motion_event": {"phase": "running"}},
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-run")
        assert entry is None

    def test_large_params_are_summarized(self):
        event = new_event(
            event_type="task_terminal",
            task_id="task-big",
            device_id="dev-1",
            payload={
                "terminal_event": {
                    "phase": "done",
                    "capability": "write_text",
                    "params": {
                        "path": [{"x": 1, "y": 2}] * 100,
                        "preview_svg": "<svg>" + "x" * 500 + "</svg>",
                        "text": "hello",
                    },
                }
            },
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-big")
        data = json.loads(entry.value)
        summary = data["params_summary"]
        assert "<present>" in summary["path"]
        assert "<present>" in summary["preview_svg"]
        assert summary["text"] == "hello"

    def test_control_capability_classified_as_control(self):
        event = new_event(
            event_type="task_terminal",
            task_id="task-home",
            device_id="dev-1",
            payload={
                "terminal_event": {
                    "phase": "done",
                    "capability": "home",
                    "params": {},
                }
            },
        )
        entry = extract_episode_from_terminal(event, "dev-1", "task-home")
        data = json.loads(entry.value)
        assert data["task_type"] == "control"


class TestExtractDeviceFailure:
    def test_failed_event_creates_failure_memory(self):
        event = new_event(
            event_type="motion_event",
            task_id="task-fail-1",
            device_id="dev-1",
            payload={
                "motion_event": {
                    "phase": "failed",
                    "capability": "run_path",
                    "error": {"code": "E_LIMIT", "reason": "limit hit"},
                }
            },
        )
        entry = extract_device_failure_from_event(event, "dev-1")
        assert entry is not None
        assert entry.type == MemoryType.DEVICE_FAILURE
        data = json.loads(entry.value)
        assert data["error_code"] == "E_LIMIT"

    def test_done_event_returns_none(self):
        event = new_event(
            event_type="motion_event",
            task_id="task-ok",
            device_id="dev-1",
            payload={"motion_event": {"phase": "done"}},
        )
        entry = extract_device_failure_from_event(event, "dev-1")
        assert entry is None

    def test_no_error_code_returns_none(self):
        event = new_event(
            event_type="motion_event",
            task_id="task-nocode",
            device_id="dev-1",
            payload={"motion_event": {"phase": "failed"}},
        )
        entry = extract_device_failure_from_event(event, "dev-1")
        assert entry is None
