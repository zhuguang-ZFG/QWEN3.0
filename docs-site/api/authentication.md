# 认证方式

LiMa 公开 API 采用 **Bearer Token** 鉴权。

## 请求头

```http
Authorization: Bearer <LIMA_API_KEY>
Content-Type: application/json
```

## 密钥类型

| 类型 | Header | 适用端点 |
|------|--------|----------|
| 公开 API Key | `Bearer lima-xxx` | `/v1/chat/completions`、`/v1/images/generations`、`/v1/models` |
| 私有 API Key | `Bearer lima-private-xxx` | `/device/v1/*`、运维、后端管理 |

公开端点通过 `access_guard.require_public_or_private_api_key` 校验，因此公开 Key 或私有 Key 均可访问。

## cURL 示例

```bash
curl -s https://chat.donglicao.com/v1/models \
  -H "Authorization: Bearer $LIMA_API_KEY"
```

## 响应示例

```json
{
  "object": "list",
  "data": [
    {"id": "claude-opus-4-7", "object": "model", "owned_by": "anthropic"},
    {"id": "gpt-5.4", "object": "model", "owned_by": "openai"},
    {"id": "lima-1.3", "object": "model", "owned_by": "donglicao"}
  ]
}
```

## 失败示例

```json
{
  "error": {
    "message": "Unauthorized",
    "type": "authentication_error"
  }
}
```

> 获取 Key 详见 [获取 API Key](/guide/api-key)。
