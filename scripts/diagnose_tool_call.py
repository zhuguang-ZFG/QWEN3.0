#!/usr/bin/env python3
"""快速诊断工具调用问题

直接发送 HTTP 请求，打印详细日志
"""

import asyncio
import json
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8090"
API_KEY = "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw"


async def test_simple_tool_call():
    """最简单的工具调用测试"""
    print("=" * 60)
    print("Simple Tool Call Test")
    print("=" * 60)

    payload = {
        "model": "lima-1.3",
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Calculate math",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expr": {"type": "string"}
                        },
                        "required": ["expr"]
                    }
                }
            }
        ],
        "stream": True
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "OpenCode/1.0",  # 触发 OpenCode 专用路径
    }

    print(f"\n[1] Sending request to {BASE_URL}/v1/chat/completions")
    print(f"    Timeout: 30s")

    start = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"[2] Client created at {time.time() - start:.2f}s")

            async with client.stream(
                "POST",
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                print(f"[3] Response received at {time.time() - start:.2f}s")
                print(f"    Status: {response.status_code}")
                print(f"    Headers: {dict(response.headers)}")

                if response.status_code != 200:
                    body = await response.aread()
                    print(f"\n❌ ERROR: {body.decode()}")
                    return False

                chunk_count = 0
                first_chunk_time = None

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    if first_chunk_time is None:
                        first_chunk_time = time.time() - start
                        print(f"[4] First chunk at {first_chunk_time:.2f}s")

                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            print(f"[5] Stream done at {time.time() - start:.2f}s")
                            break

                        chunk_count += 1
                        try:
                            data = json.loads(data_str)
                            if chunk_count <= 3:  # 只打印前3个chunk
                                print(f"    Chunk {chunk_count}: {json.dumps(data, indent=2)[:200]}")
                        except json.JSONDecodeError:
                            print(f"    Invalid JSON: {data_str[:100]}")

                total_time = time.time() - start
                print(f"\nOK Completed in {total_time:.2f}s")
                print(f"  Chunks: {chunk_count}")
                print(f"  TTFB: {first_chunk_time:.2f}s" if first_chunk_time else "  TTFB: N/A")

                return True

    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"\nTIMEOUT after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start
        print(f"\nERROR after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_without_tools():
    """对照组：不带工具的请求"""
    print("\n" + "=" * 60)
    print("Control Test: No Tools")
    print("=" * 60)

    payload = {
        "model": "lima-1.3",
        "messages": [
            {"role": "user", "content": "Say OK"}
        ],
        "stream": True
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "OpenCode/1.0",  # 触发 OpenCode 专用路径
    }

    start = time.time()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    print(f"ERROR: {body.decode()}")
                    return False

                first_chunk_time = None
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and first_chunk_time is None:
                        first_chunk_time = time.time() - start
                        break

                print(f"OK TTFB: {first_chunk_time:.2f}s" if first_chunk_time else "OK No chunks")
                return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


async def main():
    # 先测试无工具请求（验证服务可用）
    ok = await test_without_tools()
    if not ok:
        print("\nControl test failed, service may be unavailable")
        return 1

    # 再测试工具调用
    ok = await test_simple_tool_call()
    if ok:
        print("\nTool call test PASSED")
        return 0
    else:
        print("\nTool call test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
