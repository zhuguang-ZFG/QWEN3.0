# 图像生成

LiMa 通过 Pollinations.ai 提供 OpenAI 兼容的图像生成接口。

## 端点

```http
POST https://chat.donglicao.com/v1/images/generations
```

## 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 是 | 图像描述 |
| `model` | string | 否 | 默认 `lima-image` |
| `size` | string | 否 | 尺寸，格式 `宽x高`，默认 `1024x1024`，最大 `2048x2048` |
| `n` | integer | 否 | 生成数量，默认 `1`，最大 `10` |

## cURL 示例

```bash
curl -s https://chat.donglicao.com/v1/images/generations \
  -H "Authorization: Bearer $LIMA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a futuristic robot painting on canvas, cyan glow",
    "size": "1024x1024",
    "n": 1
  }'
```

## Python 示例

```python
import requests, os

resp = requests.post(
    "https://chat.donglicao.com/v1/images/generations",
    headers={"Authorization": f"Bearer {os.environ['LIMA_API_KEY']}"},
    json={
        "prompt": "一只在星云里飞行的猫，赛博朋克风格",
        "size": "1024x1024",
        "n": 2,
    },
)
for item in resp.json()["data"]:
    print(item["url"])
```

## 响应示例

```json
{
  "created": 1718880000,
  "data": [
    {
      "url": "https://image.pollinations.ai/prompt/...?width=1024&height=1024&nologo=true"
    }
  ]
}
```

## 错误示例

```json
{
  "error": "invalid image request"
}
```

常见原因：

- `size` 格式非法或超过 `2048x2048`
- `prompt` 为空
- `n` 超出 `1~10` 范围
