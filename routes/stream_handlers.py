"""流式处理器：从 server.py 提取的流式桥接和投机流式函数。

提供:
- real_stream_chunks: 同步流式 → 异步生成器桥接
- speculative_stream_chunks: 投机流式（预测 + 并行路由）
"""
import streaming as streaming_mod
from routes.v3_adapters import v3_predict, v3_select, v3_call_stream, v3_call_api


async def real_stream_chunks(backend_name: str, msgs: list, max_tokens: int = 4096, ide: str = "unknown"):
    """Bridge sync call_api_stream() to async generator.
    Runs the sync generator in a thread, pushes chunks through a queue,
    yields text chunks asynchronously.
    """
    async for chunk in streaming_mod.bridge_stream(
        backend_name, msgs, max_tokens, ide,
        call_stream_fn=v3_call_stream,
        call_fn=v3_call_api,
    ):
        yield chunk


async def speculative_stream_chunks(query: str, msgs: list, max_tokens: int = 4096, ide: str = "unknown"):
    """Speculative streaming: predict backend and start streaming immediately,
    while routing runs in parallel. If prediction is wrong, switch to correct backend.

    Yields (backend_name, text_chunk) tuples.
    """
    async for item in streaming_mod.speculative_stream(
        query, msgs, max_tokens, ide,
        predict_fn=v3_predict,
        select_fn=v3_select,
        call_stream_fn=v3_call_stream,
        call_fn=v3_call_api,
    ):
        yield item
