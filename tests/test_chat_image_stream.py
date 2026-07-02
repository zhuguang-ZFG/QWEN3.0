"""Tests for image-intent chat streaming response metadata."""

import asyncio

from chat_models import ChatRequest, Message
from routes.chat_handler_dispatch import ChatRunContext, RoutePrefs, maybe_image_response
from routes.chat_preflight import ChatPreflightResult

MOCK_NOW = 1719043200.0


def _ctx() -> ChatRunContext:
    preflight = ChatPreflightResult(
        request_messages=[{"role": "user", "content": "画一只猫"}],
        prompt_context_messages=[{"role": "user", "content": "画一只猫"}],
        system_prompt="",
        memory_recall_meta={},
        memory_session_id=None,
    )
    return ChatRunContext(
        chat_id="chat-img",
        query="画一只猫",
        t0=MOCK_NOW,
        fmt="openai",
        request_model=None,
        client_ip="127.0.0.1",
        ide_source="",
        sys_prompt_preview="",
        memory_recall_meta={},
        memory_session_id=None,
        preflight=preflight,
        prefs=RoutePrefs(prefer=None, ide_source="", use_thinking=False),
    )


def test_image_intent_stream_response_is_sse() -> None:
    recorded = []
    req = ChatRequest(model="lima", messages=[Message(role="user", content="画一只猫")], stream=True)

    response = asyncio.run(
        maybe_image_response(
            _ctx(),
            req,
            model_id="lima-1.3",
            record_request=lambda *args, **kwargs: recorded.append((args, kwargs)),
            build_pollinations_url=lambda prompt, size: f"https://img.example/{size}/{prompt}.png",
        )
    )

    assert response is not None
    assert response.media_type == "text/event-stream"
    assert recorded
