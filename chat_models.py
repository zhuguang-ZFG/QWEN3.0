"""Shared chat request models for LiMa-compatible APIs."""
from typing import Optional, Union

from pydantic import BaseModel, Field


MODEL_ID = "lima-1.3"


class Message(BaseModel):
    role: str
    content: Union[str, list] = ""


class ChatRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[Message]
    stream: bool = False
    max_tokens: Optional[int] = Field(default=1024, alias="max_tokens")
    temperature: Optional[float] = 0.7
    thinking: Optional[bool] = False


def extract_system_prompt(messages: list[Message]) -> str | None:
    """Return the first non-empty system prompt from a chat message list."""
    for msg in messages:
        if msg.role == "system" and msg.content:
            return msg.content
    return None
