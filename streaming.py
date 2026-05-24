"""
LiMa Streaming — 纯流式核心，依赖注入解耦
从 server.py 提取: _real_stream_chunks + _speculative_stream_chunks

依赖注入: 所有外部调用(call_api/call_stream/predict/select)由调用者注入
"""

import asyncio
import time
import threading
import queue as queue_mod
from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional

# 注入函数签名
CallStreamFn = Callable[[str, list, int, str], Iterator[str]]
CallApiFn = Callable[[str, list, int, str], str]
PredictFn = Callable[[str], str]
SelectFn = Callable[[str, str, str, list], tuple[str, list]]

# Async callable signatures (M2-S2)
CallStreamAsyncFn = Callable[[str, list, int, str], AsyncIterator[str]]
CallApiAsyncFn = Callable[[str, list, int, str], Awaitable[str]]


# ─── 辅助 ────────────────────────────────────────────────────────────────────

def _drain_queue(q: queue_mod.Queue):
    """清空队列防止内存泄漏"""
    while not q.empty():
        try:
            q.get_nowait()
        except queue_mod.Empty:
            break


# ─── 同步流→异步桥接 ─────────────────────────────────────────────────────────

async def bridge_stream(
    backend: str, messages: list, max_tokens: int, ide: str,
    call_stream_fn: CallStreamFn,
    call_fn: CallApiFn,
    first_chunk_timeout: float = 3.0,
) -> AsyncIterator[str]:
    """同步流→异步桥接。无chunk时 fallback 到非流式。

    Yields: text chunks (str)
    """
    q: queue_mod.Queue = queue_mod.Queue()
    cancel = threading.Event()

    def _run():
        try:
            for chunk in call_stream_fn(backend, messages, max_tokens, ide):
                if cancel.is_set():
                    return
                q.put(('chunk', chunk))
        except Exception as e:
            q.put(('error', e))
        finally:
            q.put(('done', None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    first = False
    start = time.time()

    while True:
        remaining = first_chunk_timeout - (time.time() - start)
        if remaining <= 0:
            break
        try:
            typ, val = q.get(timeout=min(remaining, 0.5))
        except queue_mod.Empty:
            continue
        if typ == 'done':
            if not first:
                cancel.set()
                thread.join(timeout=1.0)
                try:
                    result = await asyncio.to_thread(
                        call_fn, backend, messages, max_tokens, ide)
                    if result and not str(result).startswith('[ERR]'):
                        yield str(result)
                except Exception:
                    pass
                return
            return
        if typ == 'error':
            break
        if typ == 'chunk':
            first = True
            yield val

    if not first:
        cancel.set()
        thread.join(timeout=2.0)
        if thread.is_alive():
            import logging
            logging.warning(f"[STREAM] {backend} worker thread still alive after cancel+join")
        _drain_queue(q)
        try:
            result = await asyncio.to_thread(
                call_fn, backend, messages, max_tokens, ide)
            if result and not str(result).startswith('[ERR]'):
                yield str(result)
        except Exception:
            pass
        return

    # 继续消费剩余 chunk (带超时防卡死)
    while True:
        try:
            typ, val = await asyncio.to_thread(q.get, timeout=30)
        except queue_mod.Empty:
            break
        if typ == 'done':
            break
        if typ == 'chunk':
            yield val


# ─── 原生异步流式 ─────────────────────────────────────────────────────────────

async def bridge_stream_async(
    backend: str, messages: list, max_tokens: int, ide: str,
    call_stream_async_fn: CallStreamAsyncFn,
    call_api_async_fn: CallApiAsyncFn,
    first_chunk_timeout: float = 3.0,
    chunk_timeout: float = 30.0,
) -> AsyncIterator[str]:
    """Direct async streaming. No threads, no queues.

    Yields text chunks. On empty stream, falls back to call_api_async_fn.
    """
    total_text = ""
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
            total_text += chunk
            yield chunk
    except Exception:
        if not total_text:
            total_text = ""
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose:
            try:
                await aclose()
            except Exception:
                pass

    if not total_text:
        try:
            result = await call_api_async_fn(backend, messages, max_tokens, ide)
            if result and not str(result).startswith('[ERR]'):
                yield str(result)
        except Exception:
            pass


# ─── 预测流式 ────────────────────────────────────────────────────────────────

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
    """预测后端立即流式传输，同时路由在后台验证。
    预测正确→无缝流；预测错误→切换后端。

    When async callables are provided (M2-S2), uses native async streaming
    without threads.
    """
    predicted = predict_fn(query)
    predicted_msgs = messages if messages else [{"role": "user", "content": query}]

    route_task = asyncio.create_task(
        asyncio.to_thread(select_fn, query, "", ide, messages)
    )

    actual_backend = predicted
    actual_msgs = predicted_msgs
    switched = False

    # Choose async-native path when callables are available
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
                except Exception:
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
                except Exception:
                    pass
            return

        async for chunk in _streamer(actual_backend, actual_msgs):
            yield (actual_backend, chunk)

    finally:
        if not route_task.done():
            route_task.cancel()
            try:
                await route_task
            except (asyncio.CancelledError, Exception):
                pass
