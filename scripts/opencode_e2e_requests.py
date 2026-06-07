#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode E2E 测试 - 使用 requests 库（绕过 OpenAI SDK）。"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests

VPS_BASE_URL = "https://chat.donglicao.com/v1"
VPS_API_KEY = os.getenv("LIMA_API_KEY", "")

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


class TestResult:
    """测试结果封装。"""

    def __init__(self, name: str, passed: bool, message: str = "", details: dict[str, Any] | None = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}

    def __bool__(self) -> bool:
        return self.passed


def make_request(
    url: str,
    headers: dict[str, str],
    data: dict[str, Any],
    timeout: int = 30,
    stream: bool = False,
) -> requests.Response:
    """发送请求，带重试机制。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, headers=headers, json=data, stream=stream, timeout=timeout)
            return response
        except requests.Timeout as e:
            if attempt < MAX_RETRIES:
                print(f"   ⚠️  超时，重试 {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            else:
                raise
        except requests.ConnectionError as e:
            if attempt < MAX_RETRIES:
                print(f"   ⚠️  连接失败，重试 {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            else:
                raise
        except Exception as e:
            raise

    raise RuntimeError("Unreachable")


def test_simple_query() -> TestResult:
    """测试简单查询（使用 requests）。"""
    print("\n🔍 Test: Simple Query (requests library)")

    url = f"{VPS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VPS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.0",
    }
    data = {
        "model": "openai/lima-1.3",
        "messages": [{"role": "user", "content": "What is 2+2? Just answer the number."}],
        "stream": False,
    }

    print(f"   URL: {url}")
    print(f"   User-Agent: curl/8.0.0")
    print("   Sending: What is 2+2?")

    try:
        response = make_request(url, headers, data)

        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            backend = result.get("system_fingerprint", "unknown")
            print(f"✅ Response: {answer.strip()}")
            print(f"   Backend: {backend}")
            return TestResult("Simple Query", True, answer, {"backend": backend})
        else:
            message = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"❌ Failed: {message}")
            return TestResult("Simple Query", False, message)

    except requests.Timeout:
        message = "请求超时"
        print(f"❌ Error: {message}")
        return TestResult("Simple Query", False, message)
    except requests.ConnectionError as e:
        message = f"连接失败: {e}"
        print(f"❌ Error: {message}")
        return TestResult("Simple Query", False, message)
    except Exception as e:
        message = f"未知错误: {type(e).__name__}: {e}"
        print(f"❌ Error: {message}")
        return TestResult("Simple Query", False, message)


def test_streaming() -> TestResult:
    """测试流式响应（使用 requests）。"""
    print("\n🔍 Test: Streaming (requests library)")

    url = f"{VPS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VPS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.0",
    }
    data = {
        "model": "openai/lima-1.3",
        "messages": [{"role": "user", "content": "Count from 1 to 5"}],
        "stream": True,
    }

    print("   Streaming: Count from 1 to 5...")

    try:
        response = requests.post(url, headers=headers, json=data, stream=True, timeout=30)

        if response.status_code != 200:
            message = f"HTTP {response.status_code}"
            print(f"❌ Failed: {message}")
            return TestResult("Streaming", False, message)

        chunks = []
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        if chunk_data.get('choices'):
                            content = chunk_data['choices'][0].get('delta', {}).get('content')
                            if content:
                                chunks.append(content)
                                print(content, end='', flush=True)
                    except json.JSONDecodeError:
                        pass

        print()
        if len(chunks) > 0:
            print(f"✅ Streaming successful: {len(chunks)} chunks")
            return TestResult("Streaming", True, f"{len(chunks)} chunks", {"chunk_count": len(chunks)})

        message = "No chunks received"
        print(f"❌ {message}")
        return TestResult("Streaming", False, message)

    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        print(f"❌ Error: {message}")
        return TestResult("Streaming", False, message)


def test_tool_call() -> TestResult:
    """测试工具调用（使用 requests）。"""
    print("\n🔍 Test: Tool Call (requests library)")

    url = f"{VPS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VPS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.0",
    }
    data = {
        "model": "openai/lima-1.3",
        "messages": [{"role": "user", "content": "Please read README.md using the read_file tool"}],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"}
                        },
                        "required": ["path"],
                    },
                },
            }
        ],
        "stream": False,
    }

    print("   Sending: Please read README.md using the read_file tool")

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            message_data = result["choices"][0]["message"]
            if message_data.get("tool_calls"):
                tool_call = message_data["tool_calls"][0]
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                print(f"✅ Tool call: {tool_name}")
                print(f"   Arguments: {tool_args}")
                return TestResult("Tool Call", True, tool_name, {"tool": tool_name, "args": tool_args})
            else:
                message = f"No tool call: {message_data.get('content', '')[:100]}"
                print(f"⚠️  {message}")
                return TestResult("Tool Call", False, message)
        else:
            message = f"HTTP {response.status_code}"
            print(f"❌ Failed: {message}")
            return TestResult("Tool Call", False, message)

    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        print(f"❌ Error: {message}")
        return TestResult("Tool Call", False, message)


def test_ide_detection() -> TestResult:
    """测试 IDE 检测（使用 requests）。"""
    print("\n🔍 Test: IDE Detection (requests library)")

    url = f"{VPS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VPS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "OpenCode/1.0.0",  # OpenCode User-Agent
    }
    data = {
        "model": "openai/lima-1.3",
        "messages": [{"role": "user", "content": "Echo: IDE detected"}],
        "stream": False,
    }

    print("   User-Agent: OpenCode/1.0.0")
    print("   Sending: Echo: IDE detected")

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            char_count = len(content)
            print(f"✅ Response received: {char_count} chars")
            print("   Check VPS logs for 'ide_source' detection")
            return TestResult("IDE Detection", True, f"{char_count} chars", {"char_count": char_count})
        else:
            message = f"HTTP {response.status_code}"
            print(f"❌ Failed: {message}")
            return TestResult("IDE Detection", False, message)

    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        print(f"❌ Error: {message}")
        return TestResult("IDE Detection", False, message)


def test_skill_injection() -> TestResult:
    """测试 Backend-Aware Skill Reinjection（检查无重复）。"""
    print("\n🔍 Test: Skill Injection (No Duplication)")

    url = f"{VPS_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VPS_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "curl/8.0.0",
    }
    data = {
        "model": "openai/lima-1.3",
        "messages": [{"role": "user", "content": "List available skills"}],
        "stream": False,
    }

    print("   Checking skill prompt injection...")

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 检查是否有 "## LiMa Skills" 标记
            skill_marker_count = content.count("## LiMa Skills")

            if skill_marker_count == 0:
                print("✅ No skill prompt in response (expected)")
                return TestResult("Skill Injection", True, "No duplication", {"marker_count": 0})
            elif skill_marker_count == 1:
                print("✅ Skill prompt appears once")
                return TestResult("Skill Injection", True, "Single injection", {"marker_count": 1})
            else:
                message = f"Skill prompt appears {skill_marker_count} times (DUPLICATION!)"
                print(f"⚠️  {message}")
                print("   First 500 chars:")
                print(content[:500])
                return TestResult("Skill Injection", False, message, {"marker_count": skill_marker_count})
        else:
            message = f"HTTP {response.status_code}"
            print(f"❌ Failed: {message}")
            return TestResult("Skill Injection", False, message)

    except Exception as e:
        message = f"{type(e).__name__}: {e}"
        print(f"❌ Error: {message}")
        return TestResult("Skill Injection", False, message)


def main() -> int:
    print("=" * 60)
    print("OpenCode E2E 测试（使用 requests 库）")
    print("=" * 60)
    print(f"VPS: {VPS_BASE_URL}")
    print(f"重试配置: 最多 {MAX_RETRIES} 次，间隔 {RETRY_DELAY} 秒")
    print()

    if not VPS_API_KEY:
        print("Missing LIMA_API_KEY; set it before running OpenCode E2E.")
        return 2

    tests = [
        ("Simple Query", test_simple_query),
        ("Streaming", test_streaming),
        ("Tool Call", test_tool_call),
        ("IDE Detection", test_ide_detection),
        ("Skill Injection", test_skill_injection),
    ]

    results: list[TestResult] = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except KeyboardInterrupt:
            print(f"\n⚠️  测试被用户中断")
            return 130
        except Exception as e:
            print(f"❌ Test {name} crashed: {type(e).__name__}: {e}")
            results.append(TestResult(name, False, f"Crash: {e}"))
        time.sleep(1)

    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} - {result.name}")
        if not result.passed and result.message:
            print(f"       原因: {result.message}")

    print()
    print(f"总计: {passed}/{total} 通过")

    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print(f"⚠️  {total - passed} 个测试失败")

    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
