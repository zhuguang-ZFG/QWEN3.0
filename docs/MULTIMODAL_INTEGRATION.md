# LiMa 多模态能力集成方案

> 状态：执行中 | 创建：2026-05-19

## 多模态能力概览

### 已验证可用的视觉后端

| 后端 | 模型 | 视觉测试 | 延迟 | 限制 |
|------|------|----------|------|------|
| `github_gpt4o` | GPT-4o | ✅ 识别红色图片 | 4.6s | 20000 req/min |
| `google_flash_lite` | Gemini 3.1 Flash Lite | ✅ 识别红色图片 | 11.2s | 15 RPM |
| `google_flash` | Gemini 2.5 Flash | ✅ (推断) | ~1.5s | 15 RPM |

### 待手动激活

| 后端 | 模型 | 状态 | 操作 |
|------|------|------|------|
| Cloudflare | `@cf/meta/llama-3.2-11b-vision-instruct` | ❌ 需同意协议 | Dashboard 操作 |

### 图片生成能力

| 后端 | 模型 | 状态 |
|------|------|------|
| Cloudflare | `@cf/black-forest-labs/flux-2-klein-9b` | 待测试 |

## OpenAI Vision 格式 (所有后端统一)

```json
{
  "model": "gpt-4o",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "描述这张图片"},
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
  }],
  "max_tokens": 300
}
```

## 集成方案

### 路由层改动

smart_router.py 需要:
1. 检测消息中是否包含 `image_url` 类型 content
2. 如果包含图片，只路由到支持视觉的后端
3. 视觉 fallback chain: `github_gpt4o → google_flash → google_flash_lite`

### 视觉 Fallback Chain

```python
'vision': [
    'github_gpt4o',       # GPT-4o (4.6s, 最强视觉)
    'google_flash',       # Gemini 2.5 Flash (1.5s, 快速)
    'google_flash_lite',  # Gemini 3.1 Flash Lite (11s, 兜底)
]
```

### 图片输入格式兼容

所有已验证后端都支持 OpenAI Vision 格式:
- `data:image/png;base64,...` (base64 内联)
- `https://...` (URL 引用，部分后端支持)

## 验收标准

- [ ] 视觉消息正确路由到支持视觉的后端
- [ ] base64 图片输入正常工作
- [ ] 非视觉消息不受影响
- [ ] fallback chain 在首选后端失败时正确降级
