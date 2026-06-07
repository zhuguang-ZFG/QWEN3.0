"""OpenAI SSE stream generator for chat completions (CQ-014 slice 4)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import health_tracker
import http_caller
import routing_engine
import routing_facade
from http_errors import BackendError
from orchestrate import orchestrate
from response_builder import _split_sentences, build_stream_chunk
from routes.chat_support import thinking_route
from routes.stream_handlers import real_stream_chunks_async, speculative_stream_chunks
from routes.v3_adapters import v3_route
from streaming_events import build_usage_chunk

FALLBACK_MSG = "抱歉，所有后端暂不可用，请稍后重试。可尝试 /model fast 切换快速模式。"
_META_PREFIX = "__LIMA_META__:"


def _get_fallback_backends(
    primary: str,
    messages: list,
    ide_source: str = "",
) -> list[str]:
    """Get ranked fallback backends excluding the primary.

    Uses the routing engine to select healthy backends and returns
    all except the primary as fallback candidates (up to 3).

    Args:
        primary: The primary backend name to exclude from fallbacks.
        messages: Conversation messages (unused, reserved for future routing).
        ide_source: IDE source identifier; selects 'ide' req_type if set.

    Returns:
        List of fallback backend names (max 3), excluding the primary.
    """
    try:
        import health_tracker
        import routing_engine
        req_type = "ide" if ide_source else "chat"
        hmap = health_tracker.get_health_map()
        backends = routing_engine.select(req_type, hmap)
        # Remove primary from fallbacks
        return [b for b in backends if b != primary][:3]
    except Exception:
        return []


def _extract_meta(chunk: str) -> dict | None:
    """Extract __LIMA_META__ metadata from a stream chunk. Returns None if not metadata."""
    if chunk.startswith(_META_PREFIX):
        try:
            import json
            return json.loads(chunk[len(_META_PREFIX):])
        except (json.JSONDecodeError, ValueError):
            pass
    return None

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
    model: str = "",
    reasoning_effort: str | None = None,
    has_tools: bool = False,
    sampling: dict | None = None,
):
    """SSE generator: speculative streaming with orchestration/thinking fallbacks."""
    messages = messages or []
    build_url = _build_pollinations_url
    last_resort = _last_resort_call

    is_image, image_prompt = routing_facade.detect_image_intent(query)
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
                    model=model,
                    sampling=sampling,
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
    last_backend = prefer or "unknown"
    last_usage: dict | None = None

    # ── Backend-aware skill injection for streaming paths ──
    # The non-stream path injects via routing_engine.route().
    # Streaming paths that bypass route() need their own injection.
    if not use_orchestration and not use_thinking:
        try:
            from routing_engine_skills import apply_backend_aware_skills
            _skill_backend = prefer or ""
            messages = apply_backend_aware_skills(
                messages, _skill_backend,
                ide_source=ide_source, system_prompt=sys_prompt_preview,
            )
        except Exception as _e:
            logging.getLogger(__name__).debug("stream skill injection failed: %s", _e)

    streamed_text = ""
    stream_backend = prefer or "unknown"

    if prefer and not has_tools:
        fallbacks = _get_fallback_backends(prefer, messages, ide_source)
        failover_events = []

        def _track_failover(failed_b, new_b, state):
            failover_events.append({
                "failed": failed_b, "replaced_by": new_b,
                "chunks_before": state.chunk_count,
            })
            try:
                from streaming_failover_metrics import record_stream_failover
                record_stream_failover(failed_b, new_b, state.snapshot())
            except ImportError:
                logging.getLogger(__name__).debug(
                    "streaming_failover_metrics not available",
                    exc_info=True,
                )
            except Exception as exc:
                logging.getLogger(__name__).debug(
                    "stream failover metric recording failed: %s",
                    type(exc).__name__,
                )

        async for chunk in real_stream_chunks_async(
            prefer, messages, 4096, ide_source,
            fallback_backends=fallbacks,
            on_failover=_track_failover,
            sampling=sampling,
        ):
            meta = _extract_meta(chunk)
            if meta:
                if "usage" in meta:
                    last_usage = meta["usage"]
                continue
            streamed_any = True
            from response_cleaner import clean_response
            chunk = clean_response(chunk, prefer) or chunk
            streamed_text += chunk
            yield build_stream_chunk(chat_id, chunk)
        if streamed_any:
            stream_backend = prefer
            yield build_stream_chunk(chat_id, "", finish=True)
            if last_usage:
                yield build_usage_chunk(chat_id, last_usage)
            yield "data: [DONE]\n\n"
            return

    spec_fallbacks = _get_fallback_backends(
        prefer or "unknown", messages, ide_source
    )
    async for _backend, chunk in speculative_stream_chunks(
        query, messages, 4096, ide_source,
        fallback_backends=spec_fallbacks,
        sampling=sampling,
    ):
        meta = _extract_meta(chunk)
        if meta:
            if "usage" in meta:
                last_usage = meta["usage"]
            continue
        streamed_any = True
        last_backend = _backend
        from response_cleaner import clean_response
        chunk = clean_response(chunk, _backend) or chunk
        streamed_text += chunk
        stream_backend = _backend
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
                lambda b, m, t: http_caller.call_api(b, m, t, sampling=sampling),
                messages,
                4096,
            )
            last_backend = _backend
            content = answer if answer else ""
        except BackendError as exc:
            if getattr(exc, "is_overflow", False):
                from opencode_error_adapter import build_overflow_sse_chunk, extract_overflow_message
                yield build_overflow_sse_chunk(chat_id, extract_overflow_message(exc))
                yield "data: [DONE]\n\n"
                return
            logging.getLogger(__name__).debug("fallback execute failed: %s", type(exc).__name__)
            content = ""
        except Exception as exc:
            logging.getLogger(__name__).debug("fallback execute failed: %s", type(exc).__name__)
            content = ""
        from response_cleaner import clean_response
        content = clean_response(content, "") or content
        if not content or content.startswith("[ERR]"):
            content = (last_resort(messages) if last_resort else "") or FALLBACK_MSG
        for sentence in _split_sentences(content):
            yield build_stream_chunk(chat_id, sentence)
            await asyncio.sleep(0.02)
        streamed_text = content
        stream_backend = last_backend

    # ── Post-stream finalization (sticky pin, cache, integrations) ──
    try:
        from routing_engine_postprocess import finalize_route
        finalize_route(
            final_backend=stream_backend, answer=streamed_text,
            backends=[stream_backend], messages=messages,
            messages_injected=messages,
            req_type="ide" if ide_source else "chat",
            scenario="coding" if ide_source else "general",
            ms=0,
        )
    except Exception as _e:
        logging.getLogger(__name__).debug("stream finalize_route failed: %s", _e)

    yield build_stream_chunk(chat_id, "", finish=True)
    if last_usage:
        yield build_usage_chunk(chat_id, last_usage)
    yield "data: [DONE]\n\n"
