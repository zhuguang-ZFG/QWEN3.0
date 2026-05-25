"""Channel Gateway service - dedupe, auth, command dispatch, response building.

V1: guest experience bot. Guests get safe chat/code-help/draw-demo/demo/about/reset.
Owner-only commands (/code-task /device /status /artifact /memory) are rejected for guests.
"""

from channel_gateway.commands import parse_command, is_owner_only
from channel_gateway.models import (
    BindingRole,
    BindingStatus,
    InboundMessage,
    OutboundReply,
)
from channel_gateway.store import ChannelStore

_CMD_ALLOWED_WHEN_PAUSED = frozenset({"resume", "unbind", "help"})
_CMD_ALLOWED_WHEN_UNBOUND = frozenset({"bind", "help"})

_OWNER_ONLY_HELP_HINT = (
    "Owner-only commands (/code-task, /device, /status, /artifact, /memory) "
    "are not available for guest users."
)

_HELP_TEXT = (
    "LiMa WeChat Assistant (Guest)\n"
    "/chat <msg> - Chat with LiMa\n"
    "/code <question> - Code explanation/suggestion\n"
    "/draw <prompt> - Preview a path demo\n"
    "/demo - Guided LiMa capability demo\n"
    "/about - What is LiMa?\n"
    "/reset - Clear your chat session\n"
    "/pause - Pause this chat\n"
    "/resume - Resume this chat\n"
    "/unbind - Unbind this account\n"
    "/help - Show this help\n"
    "/bind <code> - Bind your WeChat to LiMa"
)

_DEMO_TEXT = (
    "LiMa Demo - try these:\n"
    "/chat What is a debounce function?\n"
    "/code Explain async/await in Python\n"
    "/draw LiMa\n"
    "/about\n"
    "/reset"
)

_ABOUT_TEXT = (
    "LiMa is a private coding and hardware assistant. "
    "It routes your questions through many free AI backends to give fast, helpful answers. "
    "This WeChat bot is a lightweight demo - it can chat, explain code, and preview drawings. "
    "For the full LiMa experience (code tasks, device control, memory), use the IDE or desktop client."
)


class ChannelService:
    """Processes normalized inbound messages from a channel sidecar."""

    def __init__(self, store: ChannelStore, enabled: bool = True):
        self._store = store
        self._enabled = enabled
        # Guest-safe handlers injected for testing
        self._chat_handler = lambda user, msg: f"[chat] {msg}"
        self._code_handler = lambda user, q: f"[code help] {q}"
        self._draw_handler = lambda user, prompt: f"[draw demo] {prompt}"
        self._demo_handler = lambda user: _DEMO_TEXT
        self._about_handler = lambda user: _ABOUT_TEXT
        self._reset_handler = lambda user: "[session cleared]"
        # Owner-only handlers — lazily built on first access
        self._owner_code_task_handler = None
        self._owner_device_handler = None
        self._owner_status_handler = None
        self._owner_artifact_handler = None
        self._owner_memory_handler = None

    # -- Main Entry ----------------------------------------------------------

    def handle_message(self, msg: InboundMessage) -> OutboundReply:
        if not self._enabled:
            return OutboundReply(ok=False, error="WeChat bridge is disabled")

        if not self._store.record_message(
            message_id=msg.message_id,
            channel="wechat",
            channel_user_id_raw=msg.sender_id,
            conversation_id_raw=msg.conversation_id,
            direction="inbound",
            intent="unknown",
            summary=msg.text[:200],
        ):
            return OutboundReply(ok=False, error="duplicate message")

        cmd = parse_command(msg.text)
        binding = self._store.get_binding_by_channel_user("wechat", msg.sender_id)

        # Auth: unbound / revoked
        if binding is None or binding.status == BindingStatus.REVOKED:
            return self._handle_unbound(msg, cmd)

        # Auth: paused
        if binding.status == BindingStatus.PAUSED:
            return self._handle_paused(msg, cmd)

        # Owner-only command rejection for guests
        if is_owner_only(cmd.intent) and binding.role != BindingRole.OWNER:
            return self._reject_owner_only(cmd)

        return self._dispatch(binding, msg, cmd)

    # -- Auth States ---------------------------------------------------------

    def _handle_unbound(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent == "bind":
            return self._do_bind(msg.sender_id, cmd.args)
        if cmd.intent == "help":
            return OutboundReply(ok=True, reply={"text": _HELP_TEXT})
        return OutboundReply(
            ok=False,
            error="Please bind first. Get a code and send /bind <code>",
        )

    def _handle_paused(self, msg: InboundMessage, cmd) -> OutboundReply:
        if cmd.intent in _CMD_ALLOWED_WHEN_PAUSED:
            return self._dispatch_state_change(msg.sender_id, cmd)
        return OutboundReply(ok=False, error="Chat paused. Send /resume to continue.")

    def _reject_owner_only(self, cmd) -> OutboundReply:
        return OutboundReply(
            ok=False,
            reply={"text": f"/{cmd.intent} is owner-only. {_OWNER_ONLY_HELP_HINT}"},
        )

    # -- Dispatch ------------------------------------------------------------

    def _dispatch(self, binding, msg: InboundMessage, cmd) -> OutboundReply:
        intent = cmd.intent

        if intent in ("pause", "resume", "unbind"):
            return self._dispatch_state_change(msg.sender_id, cmd)

        if intent == "chat":
            return self._do_chat(msg.sender_id, cmd.args)

        if intent == "code":
            return self._do_code(msg.sender_id, cmd.args)

        if intent == "draw":
            return self._do_draw(msg.sender_id, cmd.args)

        if intent == "demo":
            return OutboundReply(ok=True, reply={"text": self._demo_handler(msg.sender_id)})

        if intent == "about":
            return OutboundReply(ok=True, reply={"text": self._about_handler(msg.sender_id)})

        if intent == "reset":
            return OutboundReply(ok=True, reply={"text": self._reset_handler(msg.sender_id)})

        if intent == "help":
            return OutboundReply(ok=True, reply={"text": _HELP_TEXT})

        if intent == "code_task":
            if self._owner_code_task_handler is None:
                from channel_gateway.integrations import build_owner_code_task_handler
                self._owner_code_task_handler = build_owner_code_task_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_code_task_handler(msg.sender_id, cmd.args)},
            )

        if intent == "device":
            if self._owner_device_handler is None:
                from channel_gateway.integrations import build_owner_device_handler
                self._owner_device_handler = build_owner_device_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_device_handler(msg.sender_id, cmd.args)},
            )

        if intent == "status":
            if self._owner_status_handler is None:
                from channel_gateway.integrations import build_owner_status_handler
                self._owner_status_handler = build_owner_status_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_status_handler(msg.sender_id)},
            )

        if intent == "artifact":
            if self._owner_artifact_handler is None:
                from channel_gateway.integrations import build_owner_artifact_handler
                self._owner_artifact_handler = build_owner_artifact_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_artifact_handler(cmd.args)},
            )

        if intent == "memory":
            if self._owner_memory_handler is None:
                from channel_gateway.integrations import build_owner_memory_handler
                self._owner_memory_handler = build_owner_memory_handler()
            return OutboundReply(
                ok=True,
                reply={"text": self._owner_memory_handler(msg.sender_id, cmd.args)},
            )

        if intent == "unknown":
            return OutboundReply(
                ok=False,
                reply={"text": "Unknown command. Send /help for available commands."},
            )

        return OutboundReply(ok=False, error=f"Unhandled intent: {intent}")

    # -- State Change --------------------------------------------------------

    def _dispatch_state_change(self, sender_id: str, cmd) -> OutboundReply:
        binding = self._store.get_binding_by_channel_user("wechat", sender_id)
        if binding is None:
            return OutboundReply(ok=False, error="No binding found")

        if cmd.intent == "pause":
            self._store.set_binding_status(binding.binding_id, BindingStatus.PAUSED)
            return OutboundReply(ok=True, reply={"text": "Chat paused. Send /resume to continue."})

        if cmd.intent == "resume":
            self._store.set_binding_status(binding.binding_id, BindingStatus.ACTIVE)
            return OutboundReply(ok=True, reply={"text": "Welcome back! Chat resumed."})

        if cmd.intent == "unbind":
            self._store.set_binding_status(binding.binding_id, BindingStatus.REVOKED)
            return OutboundReply(
                ok=True,
                reply={"text": "Account unbound. Send /bind <code> to re-bind."},
            )

        return OutboundReply(ok=False, error=f"Unknown state change: {cmd.intent}")

    # -- Command Handlers ----------------------------------------------------

    def _do_bind(self, sender_id: str, code: str) -> OutboundReply:
        if not code or not code.strip():
            return OutboundReply(
                ok=False,
                reply={"text": "Usage: /bind <code>. Get a code from the LiMa operator."},
            )
        code = code.strip()
        if not self._store.validate_binding_code(code):
            return OutboundReply(
                ok=False, reply={"text": "Invalid or expired binding code."}
            )

        binding_id = f"bind_{sender_id[:20]}_{code[:6]}"
        ok = self._store.create_binding(
            binding_id=binding_id,
            channel="wechat",
            channel_user_id_raw=sender_id,
            display_name=sender_id[:20],
            lima_user_id="operator",
        )
        if not ok:
            return OutboundReply(
                ok=False, reply={"text": "Binding failed. You may already be bound."}
            )

        # Check assigned role for welcome message
        binding = self._store.get_binding_by_channel_user("wechat", sender_id)
        role = binding.role if binding else BindingRole.GUEST
        welcome = (
            f"Bound as {role}. Welcome to LiMa!\n\n{_HELP_TEXT}"
        )
        return OutboundReply(ok=True, reply={"text": welcome})

    def _do_chat(self, sender_id: str, text: str) -> OutboundReply:
        if not text.strip():
            return OutboundReply(ok=False, reply={"text": "What would you like to chat about?"})
        answer = self._chat_handler(sender_id, text.strip())
        return OutboundReply(ok=True, reply={"text": answer})

    def _do_code(self, sender_id: str, question: str) -> OutboundReply:
        if not question.strip():
            return OutboundReply(
                ok=False, reply={"text": "Usage: /code <question> for code explanation."}
            )
        answer = self._code_handler(sender_id, question.strip())
        return OutboundReply(ok=True, reply={"text": answer})

    def _do_draw(self, sender_id: str, prompt: str) -> OutboundReply:
        if not prompt.strip():
            return OutboundReply(
                ok=False, reply={"text": "Usage: /draw <prompt> for a path preview demo."}
            )
        answer = self._draw_handler(sender_id, prompt.strip())
        return OutboundReply(ok=True, reply={"text": answer})
