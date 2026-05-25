"""Tests for channel_gateway command parser - V1 guest command table."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channel_gateway.commands import parse_command, is_owner_only, MAX_TEXT_LENGTH


class TestCommandParser:
    # -- Guest Commands -------------------------------------------------

    def test_bind_command(self):
        result = parse_command("/bind 123456")
        assert result.intent == "bind"
        assert result.args == "123456"

    def test_chat_command(self):
        result = parse_command("/chat hello world")
        assert result.intent == "chat"
        assert result.args == "hello world"

    def test_plain_text_as_chat(self):
        result = parse_command("hello, how are you?")
        assert result.intent == "chat"
        assert result.args == "hello, how are you?"

    def test_code_command(self):
        result = parse_command("/code explain async/await in Python")
        assert result.intent == "code"
        assert "async/await" in result.args

    def test_draw_command(self):
        result = parse_command("/draw LiMa")
        assert result.intent == "draw"
        assert result.args == "LiMa"

    def test_demo_command(self):
        result = parse_command("/demo")
        assert result.intent == "demo"

    def test_about_command(self):
        result = parse_command("/about")
        assert result.intent == "about"

    def test_reset_command(self):
        result = parse_command("/reset")
        assert result.intent == "reset"

    def test_pause_command(self):
        result = parse_command("/pause")
        assert result.intent == "pause"

    def test_resume_command(self):
        result = parse_command("/resume")
        assert result.intent == "resume"

    def test_unbind_command(self):
        result = parse_command("/unbind")
        assert result.intent == "unbind"

    def test_help_command(self):
        result = parse_command("/help")
        assert result.intent == "help"

    # -- Owner-Only Commands (parsed but rejected in service) ------------

    def test_code_task_command(self):
        result = parse_command("/code-task fix bug in server.py")
        assert result.intent == "code_task"
        assert is_owner_only("code_task")

    def test_device_command(self):
        result = parse_command("/device write LiMa")
        assert result.intent == "device"
        assert is_owner_only("device")

    def test_status_command(self):
        result = parse_command("/status")
        assert result.intent == "status"
        assert is_owner_only("status")

    def test_artifact_command(self):
        result = parse_command("/artifact abc123")
        assert result.intent == "artifact"
        assert is_owner_only("artifact")

    def test_memory_command(self):
        result = parse_command("/memory recent")
        assert result.intent == "memory"
        assert is_owner_only("memory")

    # -- Edge Cases -----------------------------------------------------

    def test_unknown_command(self):
        result = parse_command("/foobar xyz")
        assert result.intent == "unknown"

    def test_empty_text(self):
        result = parse_command("")
        assert result.intent == "unknown"
        assert result.args == ""

    def test_whitespace_only(self):
        result = parse_command("   ")
        assert result.intent == "unknown"

    def test_guest_commands_not_owner_only(self):
        for cmd in ("chat", "code", "draw", "demo", "about", "reset",
                     "pause", "resume", "unbind", "help", "bind"):
            assert not is_owner_only(cmd), f"{cmd} should not be owner-only"

    def test_overlong_text_truncated(self):
        long_text = "x" * (MAX_TEXT_LENGTH + 100)
        result = parse_command(long_text)
        assert len(result.raw_text) <= MAX_TEXT_LENGTH
