"""OpenCode 性能基线测试

测量 OpenCode 集成场景下的关键性能指标：
- TTFB (Time To First Byte): 首字节延迟
- TTFT (Time To First Token): 首个有效 token 延迟
- TPS (Tokens Per Second): 流式输出速率
- Tool Latency: 工具调用往返延迟
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LIMA_RUN_PERF_TESTS") != "1",
    reason="OpenCode performance baseline tests are live and opt-in",
)

# 测试目标 URL（本地或 VPS）
BASE_URL = os.environ.get("LIMA_TEST_URL", "http://127.0.0.1:8090")
API_KEY = os.environ.get("LIMA_API_KEY", "test-key")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self):
        self.ttfb: float | None = None  # Time to first byte
        self.ttft: float | None = None  # Time to first token
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
        """Tokens per second"""
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


async def stream_opencode_request(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str = "lima-1.3",
) -> AsyncIterator[tuple[str, dict]]:
    """发送 OpenCode 风格的流式请求，yield (event_type, data)"""
    payload = {
        "model": model,
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


@pytest.mark.asyncio
async def test_ttfb_plain_text():
    """测量纯文本请求的首字节延迟 (TTFB)

    目标: < 2000ms
    """
    messages = [{"role": "user", "content": "Say OK"}]
    metrics = PerformanceMetrics()
    metrics.start()

    first_byte_received = False
    first_token_received = False

    async for event_type, data in stream_opencode_request(messages):
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

    print(f"\n[TTFB Plain Text] {summary}")

    assert summary["ttfb_ms"] is not None, "TTFB not measured"
    assert summary["ttfb_ms"] < 2000, f"TTFB {summary['ttfb_ms']}ms exceeds 2000ms target"


@pytest.mark.asyncio
async def test_ttfb_with_tools():
    """测量工具调用请求的首字节延迟

    目标: < 3000ms
    """
    messages = [{"role": "user", "content": "List files in current directory"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in a directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path"}
                    },
                    "required": ["path"],
                },
            },
        }
    ]

    metrics = PerformanceMetrics()
    metrics.start()

    first_byte_received = False

    async for event_type, data in stream_opencode_request(messages, tools=tools):
        if not first_byte_received:
            metrics.record_first_byte()
            first_byte_received = True
            metrics.record_chunk()

        if event_type == "chunk":
            metrics.record_chunk()

    metrics.finish()
    summary = metrics.summary()

    print(f"\n[TTFB With Tools] {summary}")

    assert summary["ttfb_ms"] is not None, "TTFB not measured"
    assert summary["ttfb_ms"] < 3000, f"TTFB {summary['ttfb_ms']}ms exceeds 3000ms target"


@pytest.mark.asyncio
async def test_streaming_tps():
    """测量流式输出速率 (TPS)

    目标: > 20 tokens/s
    """
    messages = [{"role": "user", "content": "Write a 200-word paragraph about coding"}]
    metrics = PerformanceMetrics()
    metrics.start()

    async for event_type, data in stream_opencode_request(messages):
        if event_type == "chunk":
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    # 粗略估算：每个字符 ~0.5 token
                    metrics.record_chunk(max(1, len(content) // 2))

    metrics.finish()
    summary = metrics.summary()

    print(f"\n[Streaming TPS] {summary}")

    assert summary["tps"] > 20, f"TPS {summary['tps']} below 20 tokens/s target"


@pytest.mark.asyncio
async def test_multi_turn_latency():
    """测量 5 轮对话的累计延迟

    目标: < 15s (平均每轮 < 3s)
    """
    total_start = time.time()
    turn_metrics = []

    messages = []
    for i in range(5):
        messages.append({"role": "user", "content": f"Turn {i+1}: Say OK{i+1}"})

        metrics = PerformanceMetrics()
        metrics.start()

        response_content = ""
        async for event_type, data in stream_opencode_request(messages):
            if not metrics.ttfb:
                metrics.record_first_byte()
            if event_type == "chunk":
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        response_content += content
                        metrics.record_chunk()

        metrics.finish()
        turn_metrics.append(metrics.summary())

        # 添加 assistant 响应
        messages.append({"role": "assistant", "content": response_content})

    total_time = time.time() - total_start

    print(f"\n[Multi-Turn Latency] Total: {total_time:.2f}s")
    for i, m in enumerate(turn_metrics, 1):
        print(f"  Turn {i}: {m}")

    avg_per_turn = total_time / 5
    assert total_time < 15, f"Total {total_time:.2f}s exceeds 15s target"
    assert avg_per_turn < 3, f"Avg {avg_per_turn:.2f}s exceeds 3s target"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Need concurrent load test setup")
async def test_concurrent_10_sessions():
    """测量 10 并发会话的稳定性

    目标: 成功率 > 95%
    """
    async def single_session(session_id: int) -> dict:
        """单个会话：2 轮对话"""
        try:
            messages = [
                {"role": "user", "content": f"Session {session_id}: Say OK"}
            ]

            metrics = PerformanceMetrics()
            metrics.start()

            async for event_type, _ in stream_opencode_request(messages):
                if event_type == "chunk":
                    metrics.record_chunk()

            metrics.finish()
            return {"success": True, "metrics": metrics.summary()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    tasks = [single_session(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r["success"])
    success_rate = success_count / len(results) * 100

    print(f"\n[Concurrent 10 Sessions] Success: {success_count}/10 ({success_rate}%)")
    for i, r in enumerate(results):
        if r["success"]:
            print(f"  Session {i}: {r['metrics']}")
        else:
            print(f"  Session {i}: FAILED - {r['error']}")

    assert success_rate >= 95, f"Success rate {success_rate}% below 95% target"


if __name__ == "__main__":
    # 直接运行可以输出基线报告
    import sys

    print("=" * 60)
    print("OpenCode Performance Baseline Measurement")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    sys.exit(pytest.main([__file__, "-v", "-s"]))
