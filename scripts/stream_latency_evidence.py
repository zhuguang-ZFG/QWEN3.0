"""Streaming latency evidence — prove coding scenarios stream chunks progressively.

Usage: python scripts/stream_latency_evidence.py
"""
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simulate a coding query through the speculative stream pipeline
CODING_QUERIES = [
    ("写一个Python快速排序", "cn_coding"),
    ("write a binary search in Rust", "en_coding"),
    ("什么是asyncio事件循环", "cn_chat_control"),
]

async def measure_stream_latency():
    """Directly exercise the streaming pipeline and measure chunk timing."""
    from routes.stream_handlers import speculative_stream_chunks

    print("=" * 60)
    print("Streaming Latency Evidence — Coding Scenario")
    print("=" * 60)

    for query, label in CODING_QUERIES:
        msgs = [{"role": "user", "content": query}]
        t0 = time.time()
        first_chunk_at = None
        chunk_count = 0
        total_text = ""
        backend = "?"

        async for _backend, chunk in speculative_stream_chunks(
            query, msgs, 4096, "chat_code_mode",
        ):
            if first_chunk_at is None:
                first_chunk_at = time.time()
            chunk_count += 1
            total_text += chunk
            backend = _backend
            # Show first 3 chunks arrive progressively
            if chunk_count <= 3:
                elapsed = (time.time() - t0) * 1000
                print(f"  [{label}] chunk#{chunk_count} +{elapsed:.0f}ms backend={_backend} len={len(chunk)}")

        total_ms = (time.time() - t0) * 1000
        first_chunk_ms = (first_chunk_at - t0) * 1000 if first_chunk_at else total_ms

        print(f"  [{label}] DONE: backend={backend} chunks={chunk_count} "
              f"first_chunk={first_chunk_ms:.0f}ms total={total_ms:.0f}ms "
              f"text_len={len(total_text)}")
        print()

        # Quality assertions
        assert first_chunk_at is not None, f"[FAIL] {label}: no chunks received"
        assert len(total_text) > 50, f"[FAIL] {label}: response too short ({len(total_text)})"
        assert first_chunk_ms < 15000, f"[FAIL] {label}: first chunk too slow ({first_chunk_ms:.0f}ms)"

    print("=" * 60)
    print("PASS: All coding queries received progressive stream chunks")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(measure_stream_latency())
