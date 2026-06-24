# 第一个请求

本节使用 Python 演示如何完成第一个 Chat Completions 请求，并处理流式响应。

## 非流式请求

```python
import os
import requests

api_key = os.environ["LIMA_API_KEY"]
url = "https://chat.donglicao.com/v1/chat/completions"

resp = requests.post(
    url,
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "用一句话介绍量子星云"}],
        "max_tokens": 256,
        "temperature": 0.7,
    },
)
print(resp.json()["choices"][0]["message"]["content"])
```

## 流式请求

将 `stream` 设为 `true`，服务器会以 SSE 形式逐字返回：

```python
import os
import requests

api_key = os.environ["LIMA_API_KEY"]
url = "https://chat.donglicao.com/v1/chat/completions"

resp = requests.post(
    url,
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "讲一个科幻短故事"}],
        "stream": True,
        "max_tokens": 512,
    },
    stream=True,
)

for line in resp.iter_lines():
    if line:
        text = line.decode("utf-8")
        if text.startswith("data: "):
            chunk = text[6:]
            if chunk == "[DONE]":
                break
            print(chunk, end="")
```

## 请求成功标志

- HTTP `200`
- `choices[0].message.content` 包含模型回复
- 流式响应每段以 `data: {...}` 格式输出

## 常见错误

| 现象 | 原因 | 解决 |
|------|------|------|
| `401 Unauthorized` | API Key 缺失或错误 | 检查 `Authorization` Header |
| `429 Too Many Requests` | 触发速率限制 | 降低请求频率 |
| `400 invalid_request_error` | 请求体格式错误 | 检查 JSON 字段与类型 |
