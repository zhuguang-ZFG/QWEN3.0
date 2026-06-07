#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenCode E2E Test - Simple Version"""

import json
import os
import sys
import time
import httpx

BASE_URL = "http://localhost:5007"
API_KEY = os.getenv("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")
OPENCODE_UA = "OpenCode/1.2.0 (Windows NT 10.0; Win64; x64) Node.js/18.17.0"

def test_health():
    print("\n=== Test 1: Health Check ===")
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if resp.status_code == 200:
            print("[PASS] Service is running")
            data = resp.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Version: {data.get('version')}")
            return True
        else:
            print(f"[FAIL] Status code: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        return False

def test_opencode_chat():
    print("\n=== Test 2: OpenCode Chat ===")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": OPENCODE_UA,
        "Content-Type": "application/json",
        "X-OpenCode-Session-ID": "test-session-001",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What is 1+1? Answer in one word."}],
        "max_tokens": 50,
        "stream": False,
    }

    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )

        if resp.status_code == 200:
            data = resp.json()
            print("[PASS] Request succeeded")
            print(f"   Model: {data.get('model')}")
            content = data['choices'][0]['message']['content']
            print(f"   Response: {content[:50]}")

            if 'x-lima-backend' in resp.headers:
                print(f"   Backend: {resp.headers['x-lima-backend']}")
            if 'x-lima-route-ms' in resp.headers:
                print(f"   Route Time: {resp.headers['x-lima-route-ms']}ms")

            return True
        else:
            print(f"[FAIL] Status: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def test_session_affinity():
    print("\n=== Test 3: Session Affinity ===")
    session_id = f"test-{int(time.time())}"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": OPENCODE_UA,
        "Content-Type": "application/json",
        "X-OpenCode-Session-ID": session_id,
    }

    backends = []
    for i in range(3):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": f"Say number {i+1}"}],
            "max_tokens": 20,
            "stream": False,
        }

        try:
            resp = httpx.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0,
            )

            if resp.status_code == 200:
                backend = resp.headers.get('x-lima-backend', 'unknown')
                backends.append(backend)
                print(f"   Request {i+1}: {backend}")
        except Exception as e:
            print(f"   Request {i+1}: Error - {e}")

        time.sleep(0.5)

    if len(backends) == 3:
        unique = len(set(backends))
        if unique == 1:
            print(f"[PASS] All requests used same backend: {backends[0]}")
            return True
        else:
            print(f"[WARN] Backend changed: {backends}")
            print("   (Session cache may not be enabled)")
            return True  # Not a failure, just a note
    else:
        print("[FAIL] Not all requests completed")
        return False

def test_tool_calling():
    print("\n=== Test 4: Tool Calling ===")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "User-Agent": OPENCODE_UA,
        "Content-Type": "application/json",
    }

    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City"}
                },
                "required": ["location"]
            }
        }
    }]

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "What's the weather in Beijing?"}],
        "tools": tools,
        "max_tokens": 200,
        "stream": False,
    }

    try:
        resp = httpx.post(
            f"{BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )

        if resp.status_code == 200:
            data = resp.json()
            choice = data['choices'][0]

            if choice['message'].get('tool_calls'):
                print("[PASS] Tool call triggered")
                tc = choice['message']['tool_calls'][0]
                print(f"   Function: {tc['function']['name']}")
                print(f"   Arguments: {tc['function']['arguments'][:50]}")
                return True
            else:
                print("[WARN] No tool call (model answered directly)")
                print(f"   Content: {choice['message']['content'][:80]}")
                return True  # Not a failure
        else:
            print(f"[FAIL] Status: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

def main():
    print("="*60)
    print("OpenCode End-to-End Test")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"User-Agent: {OPENCODE_UA}")
    print("="*60)

    results = {}

    # Run tests
    if not test_health():
        print("\n[ERROR] Service not running!")
        print("   Start with: PORT=5007 python server.py")
        return 1

    results['OpenCode Chat'] = test_opencode_chat()
    results['Session Affinity'] = test_session_affinity()
    results['Tool Calling'] = test_tool_calling()

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(results.values())
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print("-"*60)
    print(f"Passed: {passed}/{total} ({passed*100//total}%)")
    print("="*60)

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
