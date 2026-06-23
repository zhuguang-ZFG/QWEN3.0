"""Tests for session_memory/device_draw_memory.py — device draw memory helpers."""

from unittest.mock import patch

from session_memory.device_draw_memory import device_session_id, record_device_draw_failure, record_device_draw_turn


class TestDeviceSessionId:
    def test_format(self):
        assert device_session_id("dev123") == "device:dev123"


class TestRecordDeviceDrawFailure:
    def test_empty_device_id(self):
        with patch("session_memory.device_draw_memory.save_typed_memory") as mock:
            record_device_draw_failure("", "prompt")
            mock.assert_not_called()

    def test_empty_prompt(self):
        with patch("session_memory.device_draw_memory.save_typed_memory") as mock:
            record_device_draw_failure("dev", "")
            mock.assert_not_called()

    def test_trims_prompt(self):
        with patch("session_memory.device_draw_memory.save_typed_memory") as mock:
            long_prompt = "x" * 200
            record_device_draw_failure("dev", long_prompt)
            assert mock.call_args.kwargs["summary"] == "x" * 120


class TestRecordDeviceDrawTurn:
    def test_records_turn(self):
        with patch("session_memory.device_draw_memory.save_typed_memory") as mock:
            record_device_draw_turn("dev", "hello", status="success")
            assert mock.called
            assert mock.call_args.kwargs["session_id"] == "device:dev"

    def test_empty_prompt(self):
        with patch("session_memory.device_draw_memory.save_typed_memory") as mock:
            record_device_draw_turn("dev", "", status="success")
            mock.assert_not_called()
