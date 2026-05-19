# FreeTheAI 集成方案

> 状态：待 API Key | 创建：2026-05-19

## 获取 API Key（需人工操作）

1. 加入 Discord: https://discord.gg/freetheai (或搜索 FreeTheAI)
2. 在任意频道输入 `/signup`
3. 获得 `sk-...` 格式的 API Key
4. 设置环境变量: `export FREETHEAI_API_KEY=sk-xxxxxxxx`

## 可用端点

| 端点 | 用途 | 格式 |
|------|------|------|
| `POST /v1/chat/completions` | 对话 | OpenAI |
| `POST /v1/messages` | 对话 | Anthropic |
| `POST /v1/images/generations` | 图片生成 | OpenAI |
| `GET /v1/models` | 模型列表 | OpenAI |
| `GET /v1/health` | 健康检查 | 自定义 |

Base URL: `https://api.freetheai.xyz`

## 推荐模型（基于 provider 稳定性）

| Provider | 状态 | 推荐模型 | 用途 |
|----------|------|----------|------|
| `yng/*` | ✅ UP | yng/gemini-3-1-pro | 通用对话 |
| `kai/*` | ✅ UP | 待确认 | 通用 |
| `bbl/*` | ✅ UP | 待确认 | 通用 |
| `vhr/*` | ✅ UP | vhr/flux_dev | 图片生成 |
| `wsf/*` | ✅ UP | 待确认 | 通用 |

## 后端配置（拿到 Key 后添加）

```python
# smart_router.py BACKENDS 新增
'freetheai_gemini': {
    'url': 'https://api.freetheai.xyz/v1/chat/completions',
    'key': os.environ.get('FREETHEAI_API_KEY', ''),
    'model': 'yng/gemini-3-1-pro',
    'fmt': 'openai',
    'timeout': 30,
},
'freetheai_claude': {
    'url': 'https://api.freetheai.xyz/v1/chat/completions',
    'key': os.environ.get('FREETHEAI_API_KEY', ''),
    'model': 'kai/claude-sonnet-4-6',
    'fmt': 'openai',
    'timeout': 30,
},
```

## Fallback Chain 位置

放在 L3 层（免费但有额度限制）：
- architecture: `or_deepseek_r1` 之后
- complex_theory: `or_deepseek_r1` 之后
- code_generation: `or_qwen3_coder` 之后

## 速率限制

| Tier | 请求/分钟 | 获取方式 |
|------|-----------|----------|
| 1 | 10 | 注册即得 |
| 2 | 15 | Discord 活跃 |
| 3 | 20 | Discord 活跃 |
| 4 | 25 | Discord 活跃 |
| 5 | 35 | Discord 活跃 |

## 验证步骤（拿到 Key 后执行）

```bash
# 1. 设置环境变量
export FREETHEAI_API_KEY=sk-your-key-here

# 2. 测试连通性
curl -s https://api.freetheai.xyz/v1/models \
  -H "Authorization: Bearer $FREETHEAI_API_KEY" | python -m json.tool | head -30

# 3. 测试对话
curl -s -X POST https://api.freetheai.xyz/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FREETHEAI_API_KEY" \
  -d '{"model":"yng/gemini-3-1-pro","messages":[{"role":"user","content":"hi"}],"max_tokens":20}'

# 4. 测试流式
curl -s -N -X POST https://api.freetheai.xyz/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FREETHEAI_API_KEY" \
  -d '{"model":"yng/gemini-3-1-pro","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":20}'
```
