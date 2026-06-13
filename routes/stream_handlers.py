"""流式处理器：从 server.py 提取的流式桥接和投机流式函数。

提供:
- real_stream_chunks: 同步流式 → 异步生成器桥接（旧路径）
- real_stream_chunks_async: 原生异步流式（M2-S2，无线程）
- speculative_stream_chunks: 投机流式（预测 + 并行路由）
"""
import streaming as streaming_mod
from routes.v3_adapters import (
    v3_predict, v3_select,
    v3_call_stream, v3_call_api,
    v3_call_stream_async, v3_call_api_async,
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


async def real_stream_chunks_async(backend_name: str, msgs: list,
                                    max_tokens: int = 4096,
                                    ide: str = "unknown"):
    """Native async streaming — no threads, no queues (M2-S2)."""
    async for chunk in streaming_mod.bridge_stream_async(
        backend_name, msgs, max_tokens, ide,
        call_stream_async_fn=v3_call_stream_async,
        call_api_async_fn=v3_call_api_async,
    ):
        yield chunk


async def speculative_stream_chunks(query: str, msgs: list,
                                     max_tokens: int = 4096,
                                     ide: str = "unknown",
                                     system_prompt: str = ""):
    """Speculative streaming with async-native path (M2-S2)."""
    async for item in streaming_mod.speculative_stream(
        query, msgs, max_tokens, ide,
        predict_fn=v3_predict,
        select_fn=v3_select,
        call_stream_fn=v3_call_stream,
        call_fn=v3_call_api,
        system_prompt=system_prompt,
        call_stream_async_fn=v3_call_stream_async,
        call_api_async_fn=v3_call_api_async,
    ):
        yield item
