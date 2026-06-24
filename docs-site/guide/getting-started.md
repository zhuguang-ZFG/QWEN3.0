# 5 分钟接入

本指南帮助开发者从零开始在 5 分钟内完成首次 LiMa API 调用。

## 前置条件

- 一个 LiMa API Key（见 [获取 API Key](/guide/api-key)）
- `curl` 或任意 HTTP 客户端 / SDK
- Python 3.10+（可选，用于运行 Python 示例）

## 三步接入

### 1. 保存 API Key

::: code-group
```bash [Bash]
export LIMA_API_KEY="your_lima_api_key"
```
```powershell [PowerShell]
$env:LIMA_API_KEY="your_lima_api_key"
```
:::

### 2. 发送第一个请求

```bash
curl -s https://chat.donglicao.com/v1/chat/completions \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lima-1.3",
    "messages": [{"role": "user", "content": "你好，LiMa"}],
    "max_tokens": 512
  }'
```

### 3. 接收响应

```json
{
  "id": "chatcmpl-xxxxxxxx",
  "object": "chat.completion",
  "created": 1718880000,
  "model": "lima-1.3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是 LiMa，很高兴为你服务。"
      },
      "finish_reason": "stop"
    }
  ]
}
```

## 下一步

- 了解 [认证方式](/api/authentication)
- 查看 [Chat Completions 完整参数](/api/chat-completions)
- 尝试 [图像生成](/api/image-generations)
