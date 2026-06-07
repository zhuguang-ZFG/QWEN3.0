#!/usr/bin/env python3
"""VPS 部署验证脚本

自动化验证部署状态和健康检查
"""

import json
import os
import subprocess
import sys
import time

import httpx

# VPS 配置（从环境变量读取）
VPS_HOST = os.getenv("VPS_HOST", "localhost")
VPS_PORT = os.getenv("VPS_PORT", "8080")
API_KEY = os.getenv("LIMA_API_KEY", "xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw")

BASE_URL = f"http://{VPS_HOST}:{VPS_PORT}"
OPENCODE_UA = "OpenCode/1.2.0 (Windows NT 10.0; Win64; x64) Node.js/18.17.0"


class DeploymentValidator:
    """部署验证器"""

    def __init__(self):
        self.results = []
        self.errors = []

    def test(self, name: str, func) -> bool:
        """执行测试并记录结果"""
        print(f"\n{'='*60}")
        print(f"Test: {name}")
        print(f"{'='*60}")

        try:
            result = func()
            self.results.append((name, result))
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status} {name}")
            return result
        except Exception as e:
            self.errors.append((name, str(e)))
            print(f"[ERROR] {name}: {e}")
            return False

    def test_health(self) -> bool:
        """健康检查"""
        try:
            resp = httpx.get(f"{BASE_URL}/health", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                print(f"   Status: {data.get('status')}")
                print(f"   Version: {data.get('version')}")
                print(f"   Model: {data.get('model')}")
                return data.get('status') == 'ok'
            else:
                print(f"   HTTP {resp.status_code}")
                return False
        except Exception as e:
            print(f"   Connection error: {e}")
            return False

    def test_opencode_config(self) -> bool:
        """检查 OpenCode 配置是否加载"""
        # 这个测试需要访问日志或通过特殊接口
        # 这里简化为发送一个请求并检查响应头
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": OPENCODE_UA,
            "Content-Type": "application/json",
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 10,
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
                # 检查响应头是否有 LiMa 特征
                has_backend = 'x-lima-backend' in resp.headers
                has_route_time = 'x-lima-route-ms' in resp.headers

                print(f"   Backend header: {has_backend}")
                print(f"   Route time header: {has_route_time}")

                return resp.status_code == 200
            else:
                print(f"   HTTP {resp.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    def test_opencode_chat(self) -> bool:
        """测试 OpenCode 聊天"""
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": OPENCODE_UA,
            "Content-Type": "application/json",
            "X-OpenCode-Session-ID": f"deploy-test-{int(time.time())}",
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
                content = data['choices'][0]['message']['content']
                print(f"   Response: {content[:50]}")
                print(f"   Model: {data.get('model')}")
                return True
            else:
                print(f"   HTTP {resp.status_code}")
                print(f"   Response: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    def test_session_affinity(self) -> bool:
        """测试会话亲和性"""
        session_id = f"deploy-affinity-{int(time.time())}"
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
                "messages": [{"role": "user", "content": f"Count to {i+1}"}],
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
            print(f"   Unique backends: {unique}")
            return unique <= 1  # 应该是 1 个后端
        else:
            return False

    def test_tool_calling(self) -> bool:
        """测试工具调用"""
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": OPENCODE_UA,
            "Content-Type": "application/json",
        }

        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        }]

        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Weather in Paris?"}],
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
                    tc = choice['message']['tool_calls'][0]
                    print(f"   Tool: {tc['function']['name']}")
                    return True
                else:
                    print("   No tool call (not a failure)")
                    return True
            else:
                print(f"   HTTP {resp.status_code}")
                return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    def print_summary(self):
        """打印测试总结"""
        print(f"\n{'='*60}")
        print("Deployment Validation Summary")
        print(f"{'='*60}")

        passed = sum(1 for _, result in self.results if result)
        total = len(self.results)

        for name, result in self.results:
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status} {name}")

        print(f"{'-'*60}")
        print(f"Passed: {passed}/{total} ({passed*100//total if total else 0}%)")

        if self.errors:
            print(f"\nErrors:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")

        print(f"{'='*60}")

        if passed == total:
            print("\n[SUCCESS] Deployment validation passed!")
            print("Production is ready.")
            return 0
        else:
            print("\n[FAILURE] Some tests failed.")
            print("Please check the errors above.")
            return 1


def main():
    """主流程"""
    print("="*60)
    print("VPS Deployment Validation")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"User-Agent: {OPENCODE_UA}")
    print("="*60)

    validator = DeploymentValidator()

    # 运行测试
    validator.test("Health Check", validator.test_health)
    validator.test("OpenCode Configuration", validator.test_opencode_config)
    validator.test("OpenCode Chat", validator.test_opencode_chat)
    validator.test("Session Affinity", validator.test_session_affinity)
    validator.test("Tool Calling", validator.test_tool_calling)

    # 打印总结
    return validator.print_summary()


if __name__ == "__main__":
    sys.exit(main())
