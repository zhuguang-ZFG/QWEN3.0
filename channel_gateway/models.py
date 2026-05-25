"""Channel Gateway data models.

Dataclasses for normalized inbound/outbound messages, binding state,
command results, and audit events.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional


class BindingStatus:
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"


class BindingRole:
    GUEST = "guest"
    OWNER = "owner"


@dataclass
class ChannelBinding:
    binding_id: str
    channel: str
    channel_user_id_hash: str
    display_name: str
    lima_user_id: str
    role: str = BindingRole.GUEST
    status: str = BindingStatus.PENDING
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class ChannelBindingCode:
    code_hash: str
    lima_user_id: str
    expires_at: int
    used_at: Optional[int] = None
    created_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class ChannelMessage:
    message_id: str
    channel: str
    channel_user_id_hash: str
    conversation_id_hash: str
    direction: str  # "inbound" | "outbound"
    intent: str
    summary: str
    task_id: Optional[str] = None
    device_id: Optional[str] = None
    created_at: int = field(default_factory=lambda: int(time.time()))


class InboundMessage:
    """Normalized inbound message from a channel sidecar."""

    def __init__(
        self,
        message_id: str,
        sender_id: str,
        conversation_id: str,
        conversation_type: str = "private",
        text: str = "",
        timestamp: int = 0,
        attachments: Optional[List[dict]] = None,
        voice_transcript: str = "",
    ):
        self.message_id = message_id
        self.sender_id = sender_id
        self.conversation_id = conversation_id
        self.conversation_type = conversation_type
        self.text = text
        self.timestamp = timestamp or int(time.time())
        self.attachments = attachments or []
        self.voice_transcript = voice_transcript


@dataclass
class OutboundReply:
    ok: bool
    reply: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class CommandResult:
    intent: str
    args: str = ""
    raw_text: str = ""
