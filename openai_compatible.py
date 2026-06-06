"""OpenAI 兼容客户端 - 绕过 Cloudflare WAF。

使用 requests 库底层实现，提供类似 OpenAI SDK 的接口。
绕过 Cloudflare WAF 拦截问题。

Usage:
    from openai_compatible import OpenAICompatibleClient

    client = OpenAICompatibleClient(
        base_url="https://chat.donglicao.com/v1",
        api_key="YOUR_API_KEY",
    )

    # 非流式
    response = client.chat_completions(
        model="openai/lima-1.3",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response["choices"][0]["message"]["content"])

    # 流式
    for chunk in client.chat_completions_stream(
        model="openai/lima-1.3",
        messages=[{"role": "user", "content": "Count to 5"}],
    ):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import requests


class OpenAICompatibleClient:
    """OpenAI 兼容客户端，底层使用 requests 绕过 Cloudflare WAF。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        user_agent: str = "curl/8.0.0",
        timeout: int = 30,
    ):
        """初始化客户端。

        Args:
            base_url: API 基础 URL（如 https://chat.donglicao.com/v1）
            api_key: API Key
            user_agent: User-Agent（默认 curl/8.0.0 绕过 WAF）
            timeout: 请求超时（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user_agent = user_agent
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """获取请求头。"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

    def chat_completions(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat completions（非流式）。

        Args:
            model: 模型 ID（如 openai/lima-1.3）
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            tools: 工具定义列表
            **kwargs: 其他参数

        Returns:
            响应 dict（OpenAI 格式）

        Raises:
            requests.RequestException: 请求失败
        """
        url = f"{self.base_url}/chat/completions"
        data: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        if tools is not None:
            data["tools"] = tools

        # 合并其他参数
        data.update(kwargs)

        response = requests.post(
            url,
            headers=self._get_headers(),
            json=data,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def chat_completions_stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Chat completions（流式）。

        Args:
            model: 模型 ID
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            tools: 工具定义列表
            **kwargs: 其他参数

        Yields:
            每个流式块的内容（str）

        Raises:
            requests.RequestException: 请求失败
        """
        url = f"{self.base_url}/chat/completions"
        data: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if temperature is not None:
            data["temperature"] = temperature
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        if tools is not None:
            data["tools"] = tools

        data.update(kwargs)

        response = requests.post(
            url,
            headers=self._get_headers(),
            json=data,
            stream=True,
            timeout=self.timeout,
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue

            data_str = line_str[6:]
            if data_str == "[DONE]":
                break

            try:
                chunk_data = json.loads(data_str)
                if chunk_data.get("choices"):
                    content = chunk_data["choices"][0].get("delta", {}).get("content")
                    if content:
                        yield content
            except json.JSONDecodeError:
                pass

    def models(self) -> dict[str, Any]:
        """获取模型列表。

        Returns:
            模型列表响应

        Raises:
            requests.RequestException: 请求失败
        """
        url = f"{self.base_url}/models"
        response = requests.get(
            url,
            headers=self._get_headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()


# 便捷函数
def create_client(
    base_url: str = "https://chat.donglicao.com/v1",
    api_key: str | None = None,
) -> OpenAICompatibleClient:
    """创建客户端实例。

    Args:
        base_url: API 基础 URL
        api_key: API Key（如果为 None，从环境变量 LIMA_API_KEY 读取）

    Returns:
        客户端实例

    Raises:
        ValueError: API Key 未提供
    """
    import os

    if api_key is None:
        api_key = os.getenv("LIMA_API_KEY")
        if not api_key:
            raise ValueError("API Key not provided. Set LIMA_API_KEY env var or pass api_key parameter.")

    return OpenAICompatibleClient(base_url=base_url, api_key=api_key)


if __name__ == "__main__":
    # 示例用法
    import sys
    import io

    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    client = create_client()

    print("=== 非流式测试 ===")
    response = client.chat_completions(
        model="openai/lima-1.3",
        messages=[{"role": "user", "content": "What is 2+2? Just answer the number."}],
    )
    print(f"Response: {response['choices'][0]['message']['content']}")

    print("\n=== 流式测试 ===")
    print("Streaming: ", end="", flush=True)
    for chunk in client.chat_completions_stream(
        model="openai/lima-1.3",
        messages=[{"role": "user", "content": "Count from 1 to 3"}],
    ):
        print(chunk, end="", flush=True)
    print()

    print("\n=== 工具调用测试 ===")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"],
                },
            },
        }
    ]
    response = client.chat_completions(
        model="openai/lima-1.3",
        messages=[{"role": "user", "content": "Read README.md"}],
        tools=tools,
    )
    message = response["choices"][0]["message"]
    if message.get("tool_calls"):
        tool_call = message["tool_calls"][0]
        print(f"Tool: {tool_call['function']['name']}")
        print(f"Args: {tool_call['function']['arguments']}")
    else:
        print(f"No tool call: {message.get('content', '')[:100]}")
