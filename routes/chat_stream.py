"""OpenAI SSE stream generator for chat completions (CQ-014 slice 4)."""

from __future__ import annotations

import asyncio
from typing import Callable

import health_tracker
import http_caller
import routing_engine
import smart_router
from orchestrate import orchestrate
from response_builder import _split_sentences, build_stream_chunk
from routes.stream_handlers import speculative_stream_chunks
from routes.v3_adapters import v3_route

from routes.chat_support import thinking_route

FALLBACK_MSG = "抱歉，所有后端暂不可用，请稍后重试。可尝试 /model fast 切换快速模式。"

_last_resort_call: Callable[[list], str] | None = None
_build_pollinations_url: Callable[[str, str], str] | None = None


def inject_deps(
    *,
    last_resort_call: Callable[[list], str],
    build_pollinations_url: Callable[[str, str], str],
) -> None:
    global _last_resort_call, _build_pollinations_url
    _last_resort_call = last_resort_call
    _build_pollinations_url = build_pollinations_url


async def stream_response(
    chat_id: str,
    query: str,
    use_orchestration: bool,
    ide_source: str = "",
    sys_prompt_preview: str = "",
    use_thinking: bool = False,
    messages: list | None = None,
    prefer: str | None = None,
):
    """SSE generator: speculative streaming with orchestration/thinking fallbacks."""
    messages = messages or []
    build_url = _build_pollinations_url
    last_resort = _last_resort_call

    is_image, image_prompt = smart_router.detect_image_intent(query)
    if is_image and build_url:
        image_url = build_url(image_prompt, "1024x1024")
        content = f"![image]({image_url})\n\n已为您生成图片，点击查看。"
        yield build_stream_chunk(chat_id, content)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    if use_thinking:
        thinking_result = await thinking_route(query, 4096, ide_source)
        if thinking_result:
            content = thinking_result.get("answer", "")
        else:
            if use_orchestration:
                result = await asyncio.to_thread(orchestrate, query)
            else:
                result = await asyncio.to_thread(
                    v3_route,
                    query,
                    messages,
                    system_prompt=sys_prompt_preview,
                    ide=ide_source,
                    max_tokens=4096,
                )
            content = result.get("answer", "") if isinstance(result, dict) else str(result)
        from response_cleaner import clean_response
        content = clean_response(content, "") or content
        if not content or not content.strip():
            content = (last_resort(messages) if last_resort else "") or FALLBACK_MSG
        for sentence in _split_sentences(content):
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    if use_orchestration:
        result = await asyncio.to_thread(orchestrate, query)
        content = result.get("answer", "") if isinstance(result, dict) else str(result)
        if not content or not content.strip():
            content = (last_resort(messages) if last_resort else "") or FALLBACK_MSG
        for sentence in _split_sentences(content):
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)
        yield build_stream_chunk(chat_id, "", finish=True)
        yield "data: [DONE]\n\n"
        return

    streamed_any = False
    last_backend = "unknown"

    async for _backend, chunk in speculative_stream_chunks(query, messages, 4096, ide_source):
        streamed_any = True
        last_backend = _backend
        from response_cleaner import clean_response
        chunk = clean_response(chunk, _backend) or chunk
        yield build_stream_chunk(chat_id, chunk)

    if not streamed_any:
        try:
            backends = routing_engine.select(
                "chat" if not ide_source else "ide",
                health_tracker.get_health_map(),
            )
            _backend, answer, _ = await asyncio.to_thread(
                routing_engine.execute,
                backends,
                lambda b, m, t: http_caller.call_api(b, m, t),
                messages,
                4096,
            )
            content = answer if answer else ""
        except Exception:
            content = ""
        from response_cleaner import clean_response
        content = clean_response(content, "") or content
        if not content or content.startswith("[ERR]"):
            content = (last_resort(messages) if last_resort else "") or FALLBACK_MSG
        for sentence in _split_sentences(content):
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)

    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"
