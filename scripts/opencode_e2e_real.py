#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode CLI 真实端到端联调测试。

使用真实的 OpenCode CLI 连接 VPS 进行联调验证：
- IDE 检测
- 工具调用
- 流式响应
- Backend-Aware Skill Reinjection
- 多轮对话

Requirements:
    pip install openai  # OpenCode CLI 使用 OpenAI SDK
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# VPS 配置
VPS_BASE_URL = "https://chat.donglicao.com/v1"
# Read from .env file or use VPS key directly
try:
    from dotenv import load_dotenv
    load_dotenv()
    VPS_API_KEY = os.getenv("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")
except ImportError:
    VPS_API_KEY = "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw"

# 测试项目路径（当前仓库）
TEST_PROJECT_PATH = Path(__file__).parent.parent.absolute()


def check_opencode_installed() -> bool:
    """检查 OpenCode CLI 是否已安装。"""
    try:
        result = subprocess.run(
            ["opencode", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"✅ OpenCode CLI installed: {result.stdout.strip()}")
            return True
        print(f"❌ OpenCode CLI not found or error: {result.stderr}")
        return False
    except FileNotFoundError:
        print("❌ OpenCode CLI not installed")
        print("   Install: npm install -g @opencode/cli")
        return False
    except subprocess.TimeoutExpired:
        print("❌ OpenCode CLI command timeout")
        return False


def test_health_check() -> bool:
    """测试 VPS 健康检查。"""
    print("\n🔍 Test 1: VPS Health Check")
    try:
        import requests
        response = requests.get(
            f"{VPS_BASE_URL.replace('/v1', '')}/health",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ VPS Health: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            print(f"   Model: {data.get('model')}")
            return True
        print(f"❌ Health check failed: {response.status_code}")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_opencode_simple_query() -> bool:
    """测试简单查询（非交互式）。"""
    print("\n🔍 Test 2: Simple Query")

    # 使用 Python OpenAI SDK 模拟 OpenCode 请求
    try:
        from openai import OpenAI

        print(f"   API Key: {VPS_API_KEY[:10]}...")
        print(f"   Base URL: {VPS_BASE_URL}")

        client = OpenAI(
            base_url=VPS_BASE_URL,
            api_key=VPS_API_KEY,
            timeout=30.0,
            max_retries=0,
        )

        print("   Sending: What is 2+2?")
        response = client.chat.completions.create(
            model="openai/lima-1.3",
            messages=[
                {"role": "user", "content": "What is 2+2? Just answer the number."}
            ],
            stream=False,
        )

        answer = response.choices[0].message.content
        print(f"✅ Response: {answer.strip()}")
        return True

    except Exception as e:
        print(f"❌ Query failed: {e}")
        # Debug: print the raw error
        print(f"   Error type: {type(e).__name__}")
        if hasattr(e, 'response'):
            print(f"   Status code: {e.response.status_code}")
            print(f"   Response body: {e.response.text[:200]}")
        return False


def test_opencode_ide_detection() -> bool:
    """测试 IDE 检测（通过 User-Agent）。"""
    print("\n🔍 Test 3: IDE Detection")

    try:
        from openai import OpenAI
        import httpx

        # 创建自定义 HTTP 客户端，添加 OpenCode User-Agent
        http_client = httpx.Client(
            headers={"User-Agent": "OpenCode/1.0.0"}
        )

        client = OpenAI(
            base_url=VPS_BASE_URL,
            api_key=VPS_API_KEY,
            http_client=http_client,
        )

        print("   Sending with OpenCode User-Agent...")
        response = client.chat.completions.create(
            model="openai/lima-1.3",
            messages=[
                {"role": "user", "content": "Echo: IDE detected"}
            ],
            stream=False,
        )

        print(f"✅ Response received: {len(response.choices[0].message.content)} chars")
        print("   Check VPS logs for 'ide_source' detection")
        return True

    except Exception as e:
        print(f"❌ IDE detection test failed: {e}")
        return False


def test_opencode_tool_call() -> bool:
    """测试工具调用（file read）。"""
    print("\n🔍 Test 4: Tool Call (File Read)")

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=VPS_BASE_URL,
            api_key=VPS_API_KEY,
        )

        # 定义一个简单的工具
        tools = [
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
        ]

        print("   Sending: Please read README.md using the read_file tool")
        response = client.chat.completions.create(
            model="openai/lima-1.3",
            messages=[
                {"role": "user", "content": "Please read README.md using the read_file tool"}
            ],
            tools=tools,
            stream=False,
        )

        # 检查是否调用了工具
        message = response.choices[0].message
        if message.tool_calls:
            print(f"✅ Tool call detected: {message.tool_calls[0].function.name}")
            print(f"   Arguments: {message.tool_calls[0].function.arguments}")
            return True
        else:
            print(f"⚠️  No tool call, response: {message.content[:100]}")
            return False

    except Exception as e:
        print(f"❌ Tool call test failed: {e}")
        return False


def test_opencode_streaming() -> bool:
    """测试流式响应。"""
    print("\n🔍 Test 5: Streaming Response")

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=VPS_BASE_URL,
            api_key=VPS_API_KEY,
        )

        print("   Streaming: Count from 1 to 5...")
        chunks = []
        stream = client.chat.completions.create(
            model="openai/lima-1.3",
            messages=[
                {"role": "user", "content": "Count from 1 to 5, one number per line"}
            ],
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                chunks.append(content)
                print(content, end="", flush=True)

        print()
        if len(chunks) > 0:
            print(f"✅ Streaming successful: {len(chunks)} chunks")
            return True
        print("❌ No chunks received")
        return False

    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        return False


def test_skill_injection() -> bool:
    """测试 Backend-Aware Skill Reinjection（检查无重复）。"""
    print("\n🔍 Test 6: Skill Injection (No Duplication)")

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=VPS_BASE_URL,
            api_key=VPS_API_KEY,
        )

        print("   Checking skill prompt injection...")
        response = client.chat.completions.create(
            model="openai/lima-1.3",
            messages=[
                {"role": "user", "content": "List available skills"}
            ],
            stream=False,
        )

        content = response.choices[0].message.content

        # 检查是否有 "## LiMa Skills" 标记
        skill_marker_count = content.count("## LiMa Skills")

        if skill_marker_count == 0:
            print("✅ No skill prompt in response (expected)")
        elif skill_marker_count == 1:
            print("✅ Skill prompt appears once")
        else:
            print(f"⚠️  Skill prompt appears {skill_marker_count} times (DUPLICATION!)")
            print("   First 500 chars:")
            print(content[:500])
            return False

        return True

    except Exception as e:
        print(f"❌ Skill injection test failed: {e}")
        return False


def main() -> int:
    """运行所有测试。"""
    print("=" * 60)
    print("OpenCode CLI 真实端到端联调测试")
    print("=" * 60)
    print(f"VPS: {VPS_BASE_URL}")
    print(f"Project: {TEST_PROJECT_PATH}")
    print()

    tests = [
        ("VPS Health Check", test_health_check),
        ("Simple Query", test_opencode_simple_query),
        ("IDE Detection", test_opencode_ide_detection),
        ("Tool Call", test_opencode_tool_call),
        ("Streaming", test_opencode_streaming),
        ("Skill Injection", test_skill_injection),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test {name} crashed: {e}")
            results.append((name, False))
        time.sleep(1)  # 避免请求过快

    # 总结
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

    if passed == total:
        print("\n🎉 所有测试通过！OpenCode + LiMa 联调成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查 VPS 日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
