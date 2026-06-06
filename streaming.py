"""
LiMa Streaming — 纯流式核心，依赖注入解耦
从 server.py 提取: _real_stream_chunks + _speculative_stream_chunks

依赖注入: 所有外部调用(call_api/call_stream/predict/select)由调用者注入
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

from streaming_bridge import bridge_stream

_log = logging.getLogger(__name__)

# 注入函数签名
CallStreamFn = Callable[[str, list, int, str], Iterator[str]]
CallApiFn = Callable[[str, list, int, str], str]
PredictFn = Callable[[str], str]
SelectFn = Callable[[str, str, str, list], tuple[str, list]]

# Async callable signatures (M2-S2)
CallStreamAsyncFn = Callable[[str, list, int, str], AsyncIterator[str]]
CallApiAsyncFn = Callable[[str, list, int, str], Awaitable[str]]


async def bridge_stream_async(
    backend: str, messages: list, max_tokens: int, ide: str,
    call_stream_async_fn: CallStreamAsyncFn,
    call_api_async_fn: CallApiAsyncFn,
    first_chunk_timeout: float = 3.0,
    chunk_timeout: float = 30.0,
) -> AsyncIterator[str]:
    """Direct async streaming. No threads, no queues."""
    total_text = ""
    received_finish = False
    stream = call_stream_async_fn(backend, messages, max_tokens, ide)

    try:
        while True:
            timeout = first_chunk_timeout if not total_text else chunk_timeout
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                break

            # ── Protocol adapter: normalize finish_reason in SSE chunks ──
            try:
                from opencode_protocol_adapter import normalize_sse_line
                chunk = normalize_sse_line(chunk)
                # Track whether we received a finish_reason
                if not received_finish and '"finish_reason"' in chunk:
                    received_finish = True
            except Exception as exc:
                _log.debug("streaming: protocol adapter normalize failed", exc_info=True)

            total_text += chunk
            yield chunk
    except Exception as exc:
        if not total_text:
            total_text = ""
        _log.warning(
            "async stream read failed backend=%s: %s",
            backend,
            type(exc).__name__,
        )
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose:
            try:
                await aclose()
            except Exception as exc:
                _log.debug(
                    "async stream aclose failed backend=%s: %s",
                    backend,
                    type(exc).__name__,
                )

    # ── Protocol adapter: graceful finish if stream was truncated ──
    if total_text and not received_finish:
        try:
            from opencode_protocol_adapter import build_graceful_finish_chunk
            graceful = build_graceful_finish_chunk(model=backend)
            _log.info("stream truncated, injecting graceful finish for backend=%s", backend)
            yield graceful
            total_text += graceful
        except Exception as exc:
            _log.debug("streaming: graceful finish injection failed", exc_info=True)

    if not total_text:
        try:
            result = await call_api_async_fn(backend, messages, max_tokens, ide)
            if result and not str(result).startswith("[ERR]"):
                yield str(result)
        except Exception as exc:
            _log.warning(
                "async stream fallback call failed backend=%s: %s",
                backend,
                type(exc).__name__,
            )


async def speculative_stream(
    query: str, messages: list, max_tokens: int, ide: str,
    predict_fn: PredictFn,
    select_fn: SelectFn,
    call_stream_fn: CallStreamFn,
    call_fn: CallApiFn,
    *,
    call_stream_async_fn: CallStreamAsyncFn | None = None,
    call_api_async_fn: CallApiAsyncFn | None = None,
) -> AsyncIterator[tuple[str, str]]:
    """预测后端立即流式传输，同时路由在后台验证。"""
    predicted = predict_fn(query)
    predicted_msgs = messages if messages else [{"role": "user", "content": query}]

    route_task = asyncio.create_task(
        asyncio.to_thread(select_fn, query, "", ide, messages)
    )

    actual_backend = predicted
    actual_msgs = predicted_msgs
    switched = False

    if call_stream_async_fn and call_api_async_fn:
        _streamer = lambda b, m: bridge_stream_async(
            b, m, max_tokens, ide,
            call_stream_async_fn=call_stream_async_fn,
            call_api_async_fn=call_api_async_fn,
        )
    else:
        _streamer = lambda b, m: bridge_stream(
            b, m, max_tokens, ide,
            call_stream_fn=call_stream_fn,
            call_fn=call_fn,
        )

    try:
        async for chunk in _streamer(predicted, predicted_msgs):
            if route_task.done() and not switched:
                try:
                    actual_backend, actual_msgs = route_task.result()
                except Exception as exc:
                    _log.debug(
                        "speculative route task result failed: %s",
                        type(exc).__name__,
                    )
                    actual_backend = predicted
                    actual_msgs = predicted_msgs

                if actual_backend != predicted:
                    switched = True
                    break
            yield (actual_backend, chunk)

        if not switched:
            if not route_task.done():
                try:
                    actual_backend, actual_msgs = await route_task
                except Exception as exc:
                    _log.debug(
                        "speculative route task await failed: %s",
                        type(exc).__name__,
                    )
            return

        async for chunk in _streamer(actual_backend, actual_msgs):
            yield (actual_backend, chunk)

    finally:
        if not route_task.done():
            route_task.cancel()
            try:
                await route_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                _log.debug(
                    "speculative route task cancel failed: %s",
                    type(exc).__name__,
                )
