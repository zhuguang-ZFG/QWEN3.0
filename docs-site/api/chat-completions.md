# Chat Completions

LiMa 提供与 OpenAI 兼容的聊天补全接口，支持普通调用与 SSE 流式调用。

## 端点

```http
POST https://chat.donglicao.com/v1/chat/completions
```

## 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 否 | 默认 `lima-1.3`，也支持 `gpt-5.4`、`claude-opus-4-7` 等 |
| `messages` | array | 是 | 消息列表，每项含 `role` 与 `content` |
| `stream` | boolean | 否 | 是否流式返回，默认 `false` |
| `max_tokens` | integer | 否 | 最大生成 token 数，默认 `1024` |
| `temperature` | number | 否 | 采样温度，默认 `0.7` |
| `tools` | array | 否 | OpenAI 格式工具定义 |
| `thinking` | boolean/object | 否 | 是否启用推理过程 |

## 非流式示例

### cURL

```bash
curl -s https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lima-1.3",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 512
  }'
```

### Python

```python
import requests, os

resp = requests.post(
    "https://chat.donglicao.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['LIMA_API_KEY']}"},
    json={
        "model": "lima-1.3",
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 512,
    },
)
print(resp.json()["choices"][0]["message"]["content"])
```

### 响应

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1718880000,
  "model": "lima-1.3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么可以帮你的吗？"
      },
      "finish_reason": "stop"
    }
  ]
}
```

## 流式示例

```bash
curl -s https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lima-1.3",
    "messages": [{"role": "user", "content": "讲个故事"}],
    "stream": true,
    "max_tokens": 512
  }'
```

返回格式：

```text
data: {"id":"...","choices":[{"delta":{"content":"从前"}}]}
data: {"id":"...","choices":[{"delta":{"content":"有座山"}}]}
data: [DONE]
```

## 工具调用

LiMa 保留 OpenAI 格式 `tools` 字段，请求会进入标准路由流水线，由模型决定是否调用工具。

```json
{
  "model": "lima-1.3",
  "messages": [{"role": "user", "content": "北京今天天气"}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}
      }
    }
  ]
}
```
