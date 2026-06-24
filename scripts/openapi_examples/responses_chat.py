#!/usr/bin/env python3
"""Response examples for OpenAI-compatible chat and image endpoints."""

from __future__ import annotations

from typing import Any

from .shared import uuid


def _resp_chat_completions() -> Any:
    return {
        "id": "chatcmpl-example",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "lima-1.3",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello! How can I help you?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


def _resp_images_generations() -> Any:
    return {
        "created": 1700000000,
        "data": [
            {
                "url": "https://example.cdn/images/generated_001.png",
                "revised_prompt": "A serene mountain lake at sunrise",
            }
        ],
    }
