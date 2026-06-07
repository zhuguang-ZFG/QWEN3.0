"""
LiMa Streaming — 纯流式核心，依赖注入解耦
从 server.py 提取: _real_stream_chunks + _speculative_stream_chunks

依赖注入: 所有外部调用(call_api/call_stream/predict/select)由调用者注入
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

from streaming_bridge import bridge_stream

try:
    from streaming_state import StreamState
    from streaming_retry import (
        build_continuation_messages,
        extract_partial_from_state,
        should_attempt_failover,
    )
    _HAS_FAILOVER_DEPS = True
except ImportError:
    _HAS_FAILOVER_DEPS = False

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
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
    on_failover: Callable[[str, str, "StreamState"], None] | None = None,
) -> AsyncIterator[str]:
    """Direct async streaming with mid-stream failover to backup backends.

    When the primary backend fails mid-stream (timeout, connection error, etc.),
    this function automatically switches to the next available fallback backend,
    constructing a continuation prompt from the accumulated partial response.

    Args:
        backend: Primary backend name.
        messages: Message list for the conversation.
        max_tokens: Maximum tokens to generate.
        ide: IDE source identifier.
        call_stream_async_fn: Async streaming call function.
        call_api_async_fn: Async non-streaming call function (fallback).
        first_chunk_timeout: Timeout for the first chunk (seconds).
        chunk_timeout: Timeout for subsequent chunks (seconds).
        fallback_backends: Optional list of backup backends to try on failure.
        max_failovers: Maximum number of failover attempts.
        on_failover: Optional callback invoked on each failover.
            Signature: (failed_backend, new_backend, state) -> None.
            Useful for metrics tracking.

    Yields:
        SSE chunk strings.
    """
    # Build list of backends to try: primary + up to max_failovers fallbacks
    fallbacks = list(fallback_backends or [])
    # Remove the primary backend from fallbacks if present
    fallbacks = [b for b in fallbacks if b != backend]
    backends_to_try = [backend] + fallbacks[:max_failovers]

    # Initialize stream state tracker (uses a stub if streaming_state unavailable)
    if _HAS_FAILOVER_DEPS:
        state = StreamState(backend=backend, backends_tried=[backend])
    else:
        state = None

    current_messages = list(messages)
    current_backend = backend

    # Track whether we've received a finish across all backends
    total_text = ""
    received_finish = False

    for attempt_idx, try_backend in enumerate(backends_to_try):
        current_backend = try_backend
        if state is not None:
            state.backend = try_backend

        stream = call_stream_async_fn(try_backend, current_messages, max_tokens, ide)
        stream_failed = False
        stream_error = None

        try:
            while True:
                timeout = first_chunk_timeout if not total_text else chunk_timeout
                try:
                    chunk = await asyncio.wait_for(
                        stream.__anext__(), timeout=timeout
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    stream_failed = True
                    stream_error = f"timeout after {timeout}s on {try_backend}"
                    _log.warning(
                        "streaming: timeout on backend=%s after %ds, "
                        "chunks=%d, text_len=%d",
                        try_backend, timeout,
                        state.chunk_count if state else 0,
                        len(total_text),
                    )
                    break

                # Protocol adapter: normalize finish_reason in SSE chunks
                try:
                    from opencode_protocol_adapter import normalize_sse_line
                    chunk = normalize_sse_line(chunk)
                    if not received_finish and '"finish_reason"' in chunk:
                        received_finish = True
                        if state is not None:
                            state.received_finish = True
                except Exception:
                    _log.debug("streaming: protocol adapter normalize failed", exc_info=True)

                if state is not None:
                    state.record_chunk(chunk)
                    _track_text_from_chunk(state, chunk)
                total_text += chunk
                yield chunk

        except Exception as exc:
            stream_failed = True
            stream_error = f"{type(exc).__name__}: {exc}"
            if not total_text:
                total_text = ""
            _log.warning(
                "async stream read failed backend=%s: %s",
                try_backend,
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
                        try_backend,
                        type(exc).__name__,
                    )

        # If stream completed normally, we're done
        if not stream_failed and received_finish:
            break

        # If stream completed without finish_reason (truncated) and more backends exist
        if not stream_failed and not received_finish and total_text:
            if attempt_idx < len(backends_to_try) - 1:
                stream_failed = True
                stream_error = "stream truncated (no finish_reason)"
            else:
                # Last backend: let graceful-finish logic below handle it
                break

        # If stream failed, attempt failover
        if stream_failed and _HAS_FAILOVER_DEPS and state is not None:
            state.mark_failed(stream_error or "unknown")

            partial_text = extract_partial_from_state(state.accumulated_text)

            if not should_attempt_failover(
                partial_text,
                state.chunk_count,
                state.failover_count,
                max_failovers=max_failovers,
            ):
                break

            # Find the next backend to try
            remaining = [
                b for b in backends_to_try[attempt_idx + 1:]
                if b != try_backend
            ]
            if not remaining:
                break

            next_backend = remaining[0]
            state.mark_failover(next_backend)

            _log.info(
                "streaming: failover from %s to %s (attempt %d, "
                "partial_len=%d, chunks=%d)",
                try_backend, next_backend, state.failover_count,
                len(partial_text), state.chunk_count,
            )

            if on_failover:
                try:
                    on_failover(try_backend, next_backend, state)
                except Exception:
                    _log.debug("streaming: on_failover callback failed", exc_info=True)

            # Build continuation messages for the next backend
            current_messages = build_continuation_messages(
                current_messages, partial_text,
            )
            # Continue to next iteration of the for loop
        elif stream_failed:
            # No failover deps or no state — just stop trying backends
            break

    # Protocol adapter: graceful finish if stream was truncated
    if total_text and not received_finish:
        try:
            from opencode_protocol_adapter import build_graceful_finish_chunk
            graceful = build_graceful_finish_chunk(model=current_backend)
            _log.info(
                "stream truncated, injecting graceful finish for backend=%s",
                current_backend,
            )
            yield graceful
            total_text += graceful
        except Exception:
            _log.debug("streaming: graceful finish injection failed", exc_info=True)

    # Non-streaming fallback if no text was received at all
    if not total_text:
        try:
            result = await call_api_async_fn(
                current_backend, current_messages, max_tokens, ide
            )
            if result and not str(result).startswith("[ERR]"):
                yield str(result)
        except Exception as exc:
            _log.warning(
                "async stream fallback call failed backend=%s: %s",
                current_backend,
                type(exc).__name__,
            )


def _track_text_from_chunk(state, chunk: str) -> None:
    """Extract and accumulate text content from an SSE chunk.

    Parses OpenAI-format SSE chunks to extract the delta.content field.
    Falls back to treating the entire chunk as text if parsing fails.

    Args:
        state: The StreamState to accumulate into.
        chunk: The raw SSE chunk string.
    """
    import json as _json

    if not chunk:
        return

    # Skip metadata chunks
    if chunk.startswith("__LIMA_META__:"):
        try:
            meta = _json.loads(chunk[len("__LIMA_META__:"):].strip())
            state.record_meta(meta)
        except (ValueError, _json.JSONDecodeError):
            pass
        return

    # Try to parse as OpenAI SSE chunk
    if chunk.startswith("data: "):
        data_str = chunk[6:].strip()
        if data_str == "[DONE]":
            return
        try:
            data = _json.loads(data_str)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                text = delta.get("content", "")
                if text:
                    state.record_text(text)
                    return
            # No text in delta -- might be a finish chunk
            return
        except (ValueError, _json.JSONDecodeError, KeyError, IndexError):
            pass

    # Fallback: treat chunk as raw text
    state.record_text(chunk)


async def speculative_stream(
    query: str, messages: list, max_tokens: int, ide: str,
    predict_fn: PredictFn,
    select_fn: SelectFn,
    call_stream_fn: CallStreamFn,
    call_fn: CallApiFn,
    *,
    call_stream_async_fn: CallStreamAsyncFn | None = None,
    call_api_async_fn: CallApiAsyncFn | None = None,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
) -> AsyncIterator[tuple[str, str]]:
    """Predicted backend immediate streaming, with route validation in parallel."""
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
            fallback_backends=fallback_backends,
            max_failovers=max_failovers,
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
