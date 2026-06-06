#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode E2E 测试 - 使用 requests 库（绕过 OpenAI SDK）。"""

from __future__ import annotations

import json
import os
import sys
import time

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests

VPS_BASE_URL = "https://chat.donglicao.com/v1"
VPS_API_KEY = "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw"


def test_simple_query():
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
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            print(f"✅ Response: {answer.strip()}")
            print(f"   Backend: {result.get('system_fingerprint', 'unknown')}")
            return True
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_streaming():
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
            print(f"❌ Failed: {response.status_code}")
            return False

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
            return True
        print("❌ No chunks received")
        return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_tool_call():
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
            message = result["choices"][0]["message"]
            if message.get("tool_calls"):
                tool_call = message["tool_calls"][0]
                print(f"✅ Tool call: {tool_call['function']['name']}")
                print(f"   Arguments: {tool_call['function']['arguments']}")
                return True
            else:
                print(f"⚠️  No tool call: {message.get('content', '')[:100]}")
                return False
        else:
            print(f"❌ Failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("OpenCode E2E 测试（使用 requests 库）")
    print("=" * 60)
    print(f"VPS: {VPS_BASE_URL}")
    print()

    tests = [
        ("Simple Query", test_simple_query),
        ("Streaming", test_streaming),
        ("Tool Call", test_tool_call),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test {name} crashed: {e}")
            results.append((name, False))
        time.sleep(1)

    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print()
    print(f"总计: {passed}/{total} 通过")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
