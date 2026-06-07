"""流式处理器：从 server.py 提取的流式桥接和投机流式函数。

提供:
- real_stream_chunks: 同步流式 → 异步生成器桥接（旧路径）
- real_stream_chunks_async: 原生异步流式（M2-S2，无线程）
- speculative_stream_chunks: 投机流式（预测 + 并行路由）
"""
import streaming as streaming_mod
from routes.v3_adapters import (
    v3_call_api,
    v3_call_api_async,
    v3_call_stream,
    v3_call_stream_async,
    v3_predict,
    v3_select,
)


async def real_stream_chunks(backend_name: str, msgs: list,
                              max_tokens: int = 4096, ide: str = "unknown"):
    """Bridge sync call_api_stream() to async generator (legacy path)."""
    async for chunk in streaming_mod.bridge_stream(
        backend_name, msgs, max_tokens, ide,
        call_stream_fn=v3_call_stream,
        call_fn=v3_call_api,
    ):
        yield chunk


async def real_stream_chunks_async(
    backend_name: str, msgs: list,
    max_tokens: int = 4096,
    ide: str = "unknown",
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
    on_failover=None,
    sampling: dict | None = None,
):
    """Native async streaming with mid-stream failover support (M2-S2).

    Args:
        backend_name: Primary backend to stream from.
        msgs: Conversation messages.
        max_tokens: Maximum tokens to generate.
        ide: IDE source identifier.
        fallback_backends: Optional list of backup backends to try on failure.
        max_failovers: Maximum number of failover attempts (default 2).
        on_failover: Optional callback invoked on each failover.
            Signature: (failed_backend, new_backend, state) -> None.
    """
    async def _call_stream(backend, messages, tokens, source):
        async for chunk in v3_call_stream_async(
            backend, messages, tokens, source, sampling=sampling
        ):
            yield chunk

    async def _call_api(backend, messages, tokens, source):
        return await v3_call_api_async(
            backend, messages, tokens, source, sampling=sampling
        )

    async for chunk in streaming_mod.bridge_stream_async(
        backend_name, msgs, max_tokens, ide,
        call_stream_async_fn=_call_stream,
        call_api_async_fn=_call_api,
        fallback_backends=fallback_backends,
        max_failovers=max_failovers,
        on_failover=on_failover,
    ):
        yield chunk


async def speculative_stream_chunks(
    query: str, msgs: list,
    max_tokens: int = 4096,
    ide: str = "unknown",
    *,
    fallback_backends: list[str] | None = None,
    max_failovers: int = 2,
    sampling: dict | None = None,
):
    """Speculative streaming with failover support (M2-S2).

    Args:
        query: User query string.
        msgs: Conversation messages.
        max_tokens: Maximum tokens to generate.
        ide: IDE source identifier.
        fallback_backends: Optional list of backup backends to try on failure.
        max_failovers: Maximum number of failover attempts (default 2).
    """
    def _call_stream(backend, messages, tokens, source):
        return v3_call_stream(backend, messages, tokens, source, sampling=sampling)

    def _call_api(backend, messages, tokens, source):
        return v3_call_api(backend, messages, tokens, source, sampling=sampling)

    async def _call_stream_async(backend, messages, tokens, source):
        async for chunk in v3_call_stream_async(
            backend, messages, tokens, source, sampling=sampling
        ):
            yield chunk

    async def _call_api_async(backend, messages, tokens, source):
        return await v3_call_api_async(
            backend, messages, tokens, source, sampling=sampling
        )

    async for item in streaming_mod.speculative_stream(
        query, msgs, max_tokens, ide,
        predict_fn=v3_predict,
        select_fn=v3_select,
        call_stream_fn=_call_stream,
        call_fn=_call_api,
        call_stream_async_fn=_call_stream_async,
        call_api_async_fn=_call_api_async,
        fallback_backends=fallback_backends,
        max_failovers=max_failovers,
    ):
        yield item
