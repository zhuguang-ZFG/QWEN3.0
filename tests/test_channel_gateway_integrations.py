"""Tests for channel_gateway guest-safe integrations - chat, code help, draw demo, owner rejection."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["LIMA_CHANNEL_ID_SALT"] = "test-salt-for-channel-tests"

from channel_gateway.integrations import (
    build_chat_handler,
    build_code_handler,
    build_draw_handler,
)
from channel_gateway.owner_handlers import (
    _voice_task_from_channel_task,
    build_owner_rejection_handler,
)


class TestChannelIntegrations:
    def test_chat_handler_returns_text(self):
        def fake_route(query, messages, call_fn=None):
            class R:
                answer = "Hello from guest LiMa"
            return R()

        handler = build_chat_handler(route_fn=fake_route)
        result = handler("user-1", "hello")
        assert "Hello from guest LiMa" in result

    def test_chat_handler_guest_persona(self):
        def fake_route(query, messages, call_fn=None):
            last_msg = messages[-1]["content"] if messages else ""
            class R:
                answer = f"reply to: {last_msg}"
            return R()

        handler = build_chat_handler(route_fn=fake_route)
        result = handler("u1", "tell me a joke")
        assert "tell me a joke" in result

    def test_code_handler_explanation_only(self):
        def fake_route(query, messages, call_fn=None):
            class R:
                answer = "Async/await is a Python concurrency pattern..."
            return R()

        handler = build_code_handler(route_fn=fake_route)
        result = handler("u1", "explain async/await")
        assert "Async/await" in result

    def test_code_handler_has_guest_system_prompt(self):
        captured_messages = []

        def fake_route(query, messages, call_fn=None):
            captured_messages.extend(messages)
            class R:
                answer = "Here is the explanation."
            return R()

        handler = build_code_handler(route_fn=fake_route)
        handler("u1", "what is a closure?")
        system_msgs = [m for m in captured_messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        assert "访客" in system_msgs[0]["content"] or "guest" in system_msgs[0]["content"].lower()

    def test_draw_handler_demo_only(self):
        handler = build_draw_handler()
        result = handler("u1", "LiMa")
        assert "demo" in result.lower()
        assert "LiMa" in result
        assert "主人" in result

    def test_draw_handler_no_device_dispatch(self):
        handler = build_draw_handler()
        result = handler("u1", "test")
        assert "预览" in result
        assert "不会下发" in result or "真实设备" in result

    def test_draw_handler_uses_path_pipeline(self):
        handler = build_draw_handler()
        reply = handler("guest-1", "LiMa")
        assert "路径点数" in reply
        assert "SVG" in reply

    def test_voice_task_from_channel_task_maps_capabilities(self):
        assert _voice_task_from_channel_task({
            "capability": "write_text",
            "text": "hello",
        })["capability"] == "write_text"

        draw = _voice_task_from_channel_task({
            "capability": "draw_generated",
            "preview_svg": "M0 0 L10 10",
        })
        assert draw["capability"] == "draw_generated"
        assert draw["params"]["prompt"] == "M0 0 L10 10"

        assert _voice_task_from_channel_task({"capability": "home"})["capability"] == "home"

    def test_owner_rejection_handler(self):
        handler = build_owner_rejection_handler("status")
        result = handler("u1")
        assert "owner-only" in result

    def test_owner_rejection_device(self):
        handler = build_owner_rejection_handler("device")
        result = handler("u1", "any args")
        assert "owner-only" in result
