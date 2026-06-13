"""OpenAI SSE stream generator for chat completions (CQ-014 slice 4)."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

import router_image
from orchestrate import orchestrate
from response_builder import _split_sentences, build_stream_chunk
from routes.stream_handlers import speculative_stream_chunks
from routes.v3_adapters import v3_route

from routes.chat_support import thinking_route

FALLBACK_MSG = "抱歉，所有后端暂不可用，请稍后重试。可尝试 /model fast 切换快速模式。"

_last_resort_call: Callable[[list], str] | None = None
_build_pollinations_url: Callable[[str, str], str] | None = None
_log = logging.getLogger(__name__)


def inject_deps(
    *,
    last_resort_call: Callable[[list], str],
    build_pollinations_url: Callable[[str, str], str],
) -> None:
    global _last_resort_call, _build_pollinations_url
    _last_resort_call = last_resort_call
    _build_pollinations_url = build_pollinations_url


async def _authoritative_route(
    query: str,
    messages: list,
    *,
    sys_prompt_preview: str = "",
    ide_source: str = "",
    max_tokens: int = 4096,
    use_orchestration: bool = False,
) -> dict:
    """Non-stream fallback via orchestrate (multi-step) or v3_route (routing_engine.route)."""
    if use_orchestration:
        return await asyncio.to_thread(
            orchestrate,
            query,
            messages=messages,
            ide_source=ide_source,
            system_prompt=sys_prompt_preview,
            max_tokens=max_tokens,
        )
    return await asyncio.to_thread(
        v3_route,
        query,
        messages,
        system_prompt=sys_prompt_preview,
        ide=ide_source,
        max_tokens=max_tokens,
    )


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

    is_image, image_prompt = router_image.detect_image_intent(query)
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
            result = await _authoritative_route(
                query,
                messages,
                sys_prompt_preview=sys_prompt_preview,
                ide_source=ide_source,
                use_orchestration=use_orchestration,
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
        result = await _authoritative_route(
            query,
            messages,
            sys_prompt_preview=sys_prompt_preview,
            ide_source=ide_source,
            use_orchestration=True,
        )
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

    async for _backend, chunk in speculative_stream_chunks(
        query, messages, 4096, ide_source, system_prompt=sys_prompt_preview,
    ):
        streamed_any = True
        from response_cleaner import clean_response
        chunk = clean_response(chunk, _backend) or chunk
        yield build_stream_chunk(chat_id, chunk)

    if not streamed_any:
        try:
            result = await _authoritative_route(
                query,
                messages,
                sys_prompt_preview=sys_prompt_preview,
                ide_source=ide_source,
            )
            content = result.get("answer", "") if isinstance(result, dict) else str(result)
        except Exception as exc:
            _log.warning("stream authoritative route failed: %s", type(exc).__name__, exc_info=True)
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
