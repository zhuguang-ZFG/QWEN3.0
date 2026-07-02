"""Tests for wakeword_runtime bridge request handler (pure-function module).

Loaded via importlib because the on-disk path ``data/digital-human/...`` is not
a valid Python package name (hyphen), mirroring test_jdcloud_push_probe.py and
test_wakeword_frame_codec.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

CODEC_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "digital-human"
    / "wakeword_runtime"
    / "runtime"
    / "bridge_request_handler.py"
)

_spec = importlib.util.spec_from_file_location("bridge_request_handler", CODEC_PATH)
assert _spec is not None
assert _spec.loader is not None
bridge_request_handler = importlib.util.module_from_spec(_spec)
sys.modules["bridge_request_handler"] = bridge_request_handler
_spec.loader.exec_module(bridge_request_handler)

handle_bridge_request = bridge_request_handler.handle_bridge_request


def _wrapped_bridge() -> MagicMock:
    """Return a stub bridge whose build_message echoes its arguments as JSON."""
    bridge = MagicMock()
    bridge.build_message.side_effect = (
        lambda event_type, payload=None, request_id=None, success=True, error=None: json.dumps(
            {
                "type": event_type,
                "requestId": request_id,
                "success": success,
                "payload": payload or {},
                "error": error,
            },
            ensure_ascii=False,
        )
    )
    return bridge


def _make_raw(msg_type: str, *, request_id: str | None = None, payload: dict | None = None) -> str:
    return json.dumps({"type": msg_type, "requestId": request_id, "payload": payload or {}})


def test_invalid_json_returns_None() -> None:
    bridge = _wrapped_bridge()
    test_root = Path("/tmp/wk-fixture")
    schedule_restart = MagicMock()
    assert handle_bridge_request(bridge, "not json {", test_root, schedule_restart) is None
    bridge.publish.assert_not_called()
    schedule_restart.assert_not_called()


def test_set_wakeword_config_success_publishes_and_returns_result(tmp_path: Path) -> None:
    bridge = _wrapped_bridge()
    schedule_restart = MagicMock()
    payload = {"keywords": ["嗨小智"]}
    raw = _make_raw("set_wakeword_config", request_id="r1", payload=payload)

    # monkeypatch save_wakeword_config via patching on the module
    saved = {}

    def fake_save(p: dict, root: Path) -> dict:
        saved["payload"] = p
        saved["root"] = root
        return {"saved": True, "keywords": p["keywords"]}

    bridge_request_handler.save_wakeword_config = fake_save  # type: ignore[attr-defined]

    result = handle_bridge_request(bridge, raw, tmp_path, schedule_restart)
    # Publish on the event bus with the saved payload
    bridge.publish.assert_called_once_with("wakeword_config", {"saved": True, "keywords": ["嗨小智"]})
    # Result is a JSON message of type set_wakeword_config_result with success=True
    parsed = json.loads(result)
    assert parsed["type"] == "set_wakeword_config_result"
    assert parsed["requestId"] == "r1"
    assert parsed["success"] is True
    assert parsed["payload"] == {"saved": True, "keywords": ["嗨小智"]}
    assert saved["payload"] == payload
    assert saved["root"] == tmp_path
    schedule_restart.assert_not_called()


def test_set_wakeword_config_save_exception_returns_failure_result(tmp_path: Path) -> None:
    bridge = _wrapped_bridge()
    schedule_restart = MagicMock()
    raw = _make_raw("set_wakeword_config", request_id="r2", payload={"bad": True})

    def fake_save(p: dict, root: Path) -> dict:
        raise RuntimeError("disk full")

    bridge_request_handler.save_wakeword_config = fake_save  # type: ignore[attr-defined]

    result = handle_bridge_request(bridge, raw, tmp_path, schedule_restart)
    parsed = json.loads(result)
    assert parsed["type"] == "set_wakeword_config_result"
    assert parsed["requestId"] == "r2"
    assert parsed["success"] is False
    assert "保存唤醒词配置失败" in parsed["error"]
    assert "disk full" in parsed["error"]
    bridge.publish.assert_not_called()
    schedule_restart.assert_not_called()


def test_restart_wakeword_service_invokes_schedule_restart(tmp_path: Path) -> None:
    bridge = _wrapped_bridge()
    schedule_restart = MagicMock()
    raw = _make_raw("restart_wakeword_service", request_id="r3")

    result = handle_bridge_request(bridge, raw, tmp_path, schedule_restart)
    schedule_restart.assert_called_once_with()
    parsed = json.loads(result)
    assert parsed["type"] == "restart_wakeword_service_result"
    assert parsed["requestId"] == "r3"
    assert parsed["success"] is True
    assert parsed["payload"] == {"restarting": True}


def test_unknown_message_type_returns_failure_result(tmp_path: Path) -> None:
    bridge = _wrapped_bridge()
    schedule_restart = MagicMock()
    raw = _make_raw("unknown_type", request_id="r4")

    result = handle_bridge_request(bridge, raw, tmp_path, schedule_restart)
    parsed = json.loads(result)
    # result_type is "{message_type}_result" when message_type is non-empty
    assert parsed["type"] == "unknown_type_result"
    assert parsed["requestId"] == "r4"
    assert parsed["success"] is False
    assert "unsupported message type: unknown_type" in parsed["error"]
    schedule_restart.assert_not_called()


def test_empty_message_type_uses_fallback_result_type(tmp_path: Path) -> None:
    bridge = _wrapped_bridge()
    schedule_restart = MagicMock()
    # '{"type": "", "requestId": "r5", "payload": {}}'
    raw = json.dumps({"type": "  ", "requestId": "r5", "payload": {}})

    result = handle_bridge_request(bridge, raw, tmp_path, schedule_restart)
    parsed = json.loads(result)
    # message_type is stripped to empty -> result_type fallback is "bridge_request_result"
    assert parsed["type"] == "bridge_request_result"
    assert parsed["requestId"] == "r5"
    assert parsed["success"] is False
    schedule_restart.assert_not_called()
    bridge.publish.assert_not_called()