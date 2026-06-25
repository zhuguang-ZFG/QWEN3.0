"""OpenAI SSE stream generator for chat completions (CQ-014 slice 4)."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, Callable

import routing_intent
from response_builder import build_stream_chunk, stream_sentences
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
    """Non-stream fallback via v3_route (routing_engine.route)."""
    return await asyncio.to_thread(
        v3_route,
        query,
        messages,
        system_prompt=sys_prompt_preview,
        ide=ide_source,
        max_tokens=max_tokens,
    )


def _ensure_content(content: str, messages: list, *, allow_error_prefix: bool = False) -> str:
    """Clean content and fall back if blank or error-prefixed."""
    from response_cleaner import clean_response

    content = clean_response(content, "") or content
    if not content or not content.strip() or (allow_error_prefix and content.startswith("[ERR]")):
        return (_last_resort_call(messages) if _last_resort_call else "") or FALLBACK_MSG
    return content


async def _resolve_image_content(query: str) -> str | None:
    """Return image markdown content if image intent is detected and URL builder exists."""
    build_url = _build_pollinations_url
    is_image, image_prompt = routing_intent.detect_image_intent(query)
    if not is_image or not build_url:
        return None
    image_url = build_url(image_prompt, "1024x1024")
    return f"![image]({image_url})\n\n已为您生成图片，点击查看。"


async def _stream_image_response(chat_id: str, query: str) -> AsyncGenerator[str, None]:
    """Yield image response chunks if the query is an image intent."""
    image_content = await _resolve_image_content(query)
    if not image_content:
        return
    yield build_stream_chunk(chat_id, image_content)
    yield build_stream_chunk(chat_id, "", finish=True)
    yield "data: [DONE]\n\n"


async def _resolve_thinking_content(
    query: str,
    messages: list,
    *,
    sys_prompt_preview: str,
    ide_source: str,
    use_orchestration: bool,
) -> str:
    """Resolve content for thinking route branch."""
    thinking_result = await thinking_route(query, 4096, ide_source)
    if thinking_result:
        return thinking_result.get("answer", "")
    result = await _authoritative_route(
        query,
        messages,
        sys_prompt_preview=sys_prompt_preview,
        ide_source=ide_source,
        use_orchestration=use_orchestration,
    )
    return result.get("answer", "") if isinstance(result, dict) else str(result)


async def _stream_thinking_response(
    chat_id: str,
    query: str,
    messages: list,
    *,
    sys_prompt_preview: str,
    ide_source: str,
    use_orchestration: bool,
) -> AsyncGenerator[str, None]:
    """Stream thinking route result as sentence chunks."""
    content = await _resolve_thinking_content(
        query,
        messages,
        sys_prompt_preview=sys_prompt_preview,
        ide_source=ide_source,
        use_orchestration=use_orchestration,
    )
    async for chunk in stream_sentences(chat_id, _ensure_content(content, messages)):
        yield chunk


async def _resolve_authoritative_content(
    query: str,
    messages: list,
    *,
    sys_prompt_preview: str,
    ide_source: str,
) -> str:
    """Resolve content from authoritative route with exception logging."""
    try:
        result = await _authoritative_route(
            query,
            messages,
            sys_prompt_preview=sys_prompt_preview,
            ide_source=ide_source,
        )
        return result.get("answer", "") if isinstance(result, dict) else str(result)
    except Exception as exc:
        _log.warning("stream authoritative route failed: %s", type(exc).__name__, exc_info=True)
        return ""


async def _stream_orchestration(
    query: str,
    messages: list,
    chat_id: str,
    *,
    sys_prompt_preview: str,
    ide_source: str,
) -> AsyncGenerator[str, None]:
    """Stream orchestration route result as sentence chunks."""
    result = await _authoritative_route(
        query,
        messages,
        sys_prompt_preview=sys_prompt_preview,
        ide_source=ide_source,
        use_orchestration=True,
    )
    answer = result.get("answer", "") if isinstance(result, dict) else str(result)
    content = _ensure_content(answer, messages)
    async for chunk in stream_sentences(chat_id, content):
        yield chunk


async def _stream_speculative(
    query: str,
    messages: list,
    chat_id: str,
    *,
    sys_prompt_preview: str,
    ide_source: str,
    prefer: str | None,
) -> AsyncGenerator[str, None]:
    """Try speculative streaming and fall back to authoritative route if needed."""
    from response_cleaner import clean_response

    streamed_any = False
    async for _backend, chunk in speculative_stream_chunks(
        query,
        messages,
        4096,
        ide_source,
        system_prompt=sys_prompt_preview,
        preferred_backend=prefer or "",
    ):
        streamed_any = True
        chunk = clean_response(chunk, _backend) or chunk
        yield build_stream_chunk(chat_id, chunk)

    if not streamed_any:
        content = await _resolve_authoritative_content(
            query,
            messages,
            sys_prompt_preview=sys_prompt_preview,
            ide_source=ide_source,
        )
        content = _ensure_content(content, messages, allow_error_prefix=True)
        async for chunk in stream_sentences(chat_id, content):
            yield chunk


async def _stream_text_response(
    chat_id: str,
    query: str,
    messages: list,
    *,
    sys_prompt_preview: str,
    ide_source: str,
    use_orchestration: bool,
    use_thinking: bool,
    prefer: str | None,
) -> AsyncGenerator[str, None]:
    """Route the non-image request to the right streaming backend branch."""
    if use_thinking:
        async for chunk in _stream_thinking_response(
            chat_id,
            query,
            messages,
            sys_prompt_preview=sys_prompt_preview,
            ide_source=ide_source,
            use_orchestration=use_orchestration,
        ):
            yield chunk
        return

    if use_orchestration:
        async for chunk in _stream_orchestration(
            query,
            messages,
            chat_id,
            sys_prompt_preview=sys_prompt_preview,
            ide_source=ide_source,
        ):
            yield chunk
        return

    async for chunk in _stream_speculative(
        query,
        messages,
        chat_id,
        sys_prompt_preview=sys_prompt_preview,
        ide_source=ide_source,
        prefer=prefer,
    ):
        yield chunk


async def stream_response(
    chat_id: str,
    query: str,
    use_orchestration: bool,
    ide_source: str = "",
    sys_prompt_preview: str = "",
    use_thinking: bool = False,
    messages: list | None = None,
    prefer: str | None = None,
) -> AsyncGenerator[str, None]:
    """SSE generator: speculative streaming with orchestration/thinking fallbacks."""
    messages = messages or []

    image_chunks = [chunk async for chunk in _stream_image_response(chat_id, query)]
    if image_chunks:
        for chunk in image_chunks:
            yield chunk
        return

    async for chunk in _stream_text_response(
        chat_id,
        query,
        messages,
        sys_prompt_preview=sys_prompt_preview,
        ide_source=ide_source,
        use_orchestration=use_orchestration,
        use_thinking=use_thinking,
        prefer=prefer,
    ):
        yield chunk
