#!/usr/bin/env python3
"""诊断 chat.donglicao 深度思考和视频模式问题"""

import asyncio
import json
import sys

import httpx

BASE_URL = "http://127.0.0.1:8090"
API_KEY = "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw"


async def test_thinking_mode():
    """测试深度思考模式"""
    print("=" * 60)
    print("Test 1: Thinking Mode (reasoning)")
    print("=" * 60)

    payload = {
        "model": "lima-1.3",
        "messages": [
            {"role": "user", "content": "What is 157 * 234?"}
        ],
        "thinking": True,  # 启用思考模式
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Model: {result.get('model')}")
                print(f"Choices: {len(result.get('choices', []))}")

                if result.get('choices'):
                    content = result['choices'][0].get('message', {}).get('content', '')
                    print(f"Content length: {len(content)}")
                    print(f"Content preview: {content[:200]}")

                    # 检查是否有思考内容
                    if 'reasoning' in result.get('choices', [{}])[0]:
                        print("OK Reasoning content found")
                        return True
                    else:
                        print("WARN No reasoning content in response")
                        print(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                        return False
            else:
                print(f"ERROR: {response.text}")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vision_mode():
    """测试视频/图片模式"""
    print("\n" + "=" * 60)
    print("Test 2: Vision Mode (image processing)")
    print("=" * 60)

    # 使用一个简单的测试图片 URL
    payload = {
        "model": "lima-1.3",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What do you see in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                        }
                    }
                ]
            }
        ],
        "stream": False
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Model: {result.get('model')}")

                if result.get('choices'):
                    content = result['choices'][0].get('message', {}).get('content', '')
                    print(f"Content: {content[:200]}")
                    print("OK Vision request processed")
                    return True
                else:
                    print("ERROR No choices in response")
                    return False
            else:
                print(f"ERROR: {response.text}")
                return False

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    thinking_ok = await test_thinking_mode()
    vision_ok = await test_vision_mode()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Thinking mode: {'OK' if thinking_ok else 'FAILED'}")
    print(f"Vision mode: {'OK' if vision_ok else 'FAILED'}")

    if thinking_ok and vision_ok:
        print("\nAll tests PASSED")
        return 0
    else:
        print("\nSome tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
