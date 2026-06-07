#!/usr/bin/env python3
"""VPS 性能基线快速测试脚本

直接在 VPS 上运行，无需 pytest：
python3 scripts/vps_performance_check.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# VPS 本地测试
BASE_URL = os.environ.get("LIMA_TEST_URL", "http://127.0.0.1:8100")
API_KEY = os.environ.get("LIMA_API_KEY", "test-key")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


class PerformanceMetrics:
    def __init__(self):
        self.ttfb: float | None = None
        self.ttft: float | None = None
        self.total_time: float = 0.0
        self.token_count: int = 0
        self.chunk_count: int = 0
        self.start_time: float = 0.0

    def start(self):
        self.start_time = time.time()

    def record_first_byte(self):
        if self.ttfb is None:
            self.ttfb = time.time() - self.start_time

    def record_first_token(self):
        if self.ttft is None:
            self.ttft = time.time() - self.start_time

    def record_chunk(self, token_count: int = 1):
        self.chunk_count += 1
        self.token_count += token_count

    def finish(self):
        self.total_time = time.time() - self.start_time

    @property
    def tps(self) -> float:
        if self.total_time > 0:
            return self.token_count / self.total_time
        return 0.0

    def summary(self) -> dict:
        return {
            "ttfb_ms": round(self.ttfb * 1000, 2) if self.ttfb else None,
            "ttft_ms": round(self.ttft * 1000, 2) if self.ttft else None,
            "total_ms": round(self.total_time * 1000, 2),
            "token_count": self.token_count,
            "chunk_count": self.chunk_count,
            "tps": round(self.tps, 2),
        }


async def stream_request(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncIterator[tuple[str, dict]]:
    """发送流式请求"""
    payload = {
        "model": "lima-1.3",
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/v1/chat/completions",
            headers=HEADERS,
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.strip() or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        yield ("done", {})
                        return
                    try:
                        data = json.loads(data_str)
                        yield ("chunk", data)
                    except json.JSONDecodeError:
                        continue


async def test_plain_text_ttfb():
    """测试纯文本 TTFB"""
    print("\n[Test 1] Plain Text TTFB")
    print(f"Target: {BASE_URL}")
    print("-" * 60)

    messages = [{"role": "user", "content": "Say OK"}]
    metrics = PerformanceMetrics()
    metrics.start()

    try:
        first_byte_received = False
        first_token_received = False

        async for event_type, data in stream_request(messages):
            if not first_byte_received:
                metrics.record_first_byte()
                first_byte_received = True

            if event_type == "chunk":
                choices = data.get("choices", [])
                if choices and not first_token_received:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        metrics.record_first_token()
                        first_token_received = True
                        metrics.record_chunk(len(content))

        metrics.finish()
        summary = metrics.summary()

        print(f"✓ TTFB: {summary['ttfb_ms']}ms")
        print(f"  TTFT: {summary['ttft_ms']}ms")
        print(f"  Total: {summary['total_ms']}ms")
        print(f"  Tokens: {summary['token_count']}")
        print(f"  Chunks: {summary['chunk_count']}")

        if summary["ttfb_ms"] and summary["ttfb_ms"] < 2000:
            print(f"✅ PASS - TTFB under 2000ms target")
        else:
            print(f"❌ FAIL - TTFB {summary['ttfb_ms']}ms exceeds 2000ms")

        return summary

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


async def test_streaming_tps():
    """测试流式 TPS"""
    print("\n[Test 2] Streaming TPS")
    print("-" * 60)

    messages = [{"role": "user", "content": "Write a 100-word paragraph about AI"}]
    metrics = PerformanceMetrics()
    metrics.start()

    try:
        async for event_type, data in stream_request(messages):
            if event_type == "chunk":
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        metrics.record_chunk(max(1, len(content) // 2))

        metrics.finish()
        summary = metrics.summary()

        print(f"✓ Total: {summary['total_ms']}ms")
        print(f"  Tokens: {summary['token_count']}")
        print(f"  TPS: {summary['tps']}")

        if summary["tps"] > 20:
            print(f"✅ PASS - TPS {summary['tps']} exceeds 20 target")
        else:
            print(f"❌ FAIL - TPS {summary['tps']} below 20")

        return summary

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


async def test_tool_call_ttfb():
    """测试工具调用 TTFB"""
    print("\n[Test 3] Tool Call TTFB (30s timeout)")
    print("-" * 60)

    messages = [{"role": "user", "content": "List files in current directory"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
    ]

    metrics = PerformanceMetrics()
    metrics.start()

    try:
        first_byte_received = False

        async for event_type, data in stream_request(messages, tools=tools):
            if not first_byte_received:
                metrics.record_first_byte()
                first_byte_received = True
                print(f"✓ First byte received at {metrics.ttfb*1000:.1f}ms")

            if event_type == "chunk":
                metrics.record_chunk()

        metrics.finish()
        summary = metrics.summary()

        print(f"✓ Total: {summary['total_ms']}ms")
        print(f"  Chunks: {summary['chunk_count']}")

        if summary["ttfb_ms"] and summary["ttfb_ms"] < 3000:
            print(f"✅ PASS - Tool call TTFB under 3000ms")
        else:
            print(f"⚠️  WARN - Tool call TTFB {summary['ttfb_ms']}ms exceeds 3000ms")

        return summary

    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT after 60s")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


async def main():
    print("=" * 60)
    print("VPS Performance Baseline Check")
    print("=" * 60)

    results = {}

    # Test 1: Plain text TTFB
    results["plain_text"] = await test_plain_text_ttfb()

    # Test 2: Streaming TPS
    results["streaming"] = await test_streaming_tps()

    # Test 3: Tool call TTFB
    results["tool_call"] = await test_tool_call_ttfb()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    passed = 0
    failed = 0

    if results["plain_text"]:
        if results["plain_text"]["ttfb_ms"] and results["plain_text"]["ttfb_ms"] < 2000:
            passed += 1
        else:
            failed += 1

    if results["streaming"]:
        if results["streaming"]["tps"] > 20:
            passed += 1
        else:
            failed += 1

    if results["tool_call"]:
        if results["tool_call"]["ttfb_ms"] and results["tool_call"]["ttfb_ms"] < 3000:
            passed += 1
        else:
            failed += 1
    else:
        failed += 1

    print(f"\nTests: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ All performance targets met!")
        return 0
    else:
        print("❌ Some performance targets not met")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
