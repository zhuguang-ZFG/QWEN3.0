# Claude Code Tool 路由设计

> 日期: 2026-05-21
> 状态: 待确认

## 问题

Claude Code 每个请求都带 `tools` 字段（1000+ 工具定义），当前实现：
- 只路由到 5 个 LongCat 后端（Anthropic 格式）
- 不做负载均衡（总是选第一个健康的）
- 非真流式（阻塞等待完整响应再返回）
- 响应慢（28s+）

## 约束

1. **只用免费模型** — 不消耗付费 API 额度（11 个付费后端排除）
2. **必须支持 tool_use** — 后端能返回正确的 tool call 格式
3. **真流式** — 用户看到打字效果，不干等
4. **P2C 负载均衡** — 分散请求到多个后端

## 可用免费后端（66 个）

### 第一梯队：Anthropic 原生（无需格式转换，tool 支持最好）

| 后端 | 模型 | 速度 |
|------|------|------|
| longcat_chat | LongCat-Flash-Chat | ~5s |
| longcat | LongCat-2.0-Preview | ~8s |
| longcat_lite | LongCat-Flash-Lite | ~3s |
| longcat_thinking | LongCat-Flash-Thinking | ~10s |
| longcat_omni | LongCat-Flash-Omni | ~5s |

### 第二梯队：OpenAI 格式高质量（需 Anthropic↔OpenAI 转换）

| 后端 | 模型 | Tool 支持 | 速度 |
|------|------|-----------|------|
| groq_llama70b | Llama-3.3-70B | ✅ | ~2s |
| github_gpt4o | GPT-4o | ✅ | ~3s |
| github_o4_mini | o4-mini | ✅ | ~4s |
| or_deepseek_r1 | DeepSeek-V4-Flash | ✅ | ~5s |
| or_qwen3_coder | Qwen3-Coder | ✅ | ~5s |
| mistral_large | Mistral-Large | ✅ | ~4s |
| nvidia_nemotron | Nemotron-49B | ✅ | ~3s |
| cerebras_qwen235b | Qwen-3-235B | ✅ | ~3s |

## 实测结果（2026-05-21 服务器 47.112.162.80）

### 根因诊断

| 后端 | 现象 | 确切原因 | 解决方案 |
|------|------|----------|----------|
| Groq | 403 error 1010 | 缺 User-Agent 触发 Cloudflare bot 检测 | 加 UA 头 ✅ 已验证 |
| Cerebras | 403 error 1010 | 同上 | 加 UA 头 ✅ 已验证 |
| Mistral/Google | 网络不可达 | 中国服务器无法直连 | 走 GFW 代理 ✅ 已验证 |
| github_o4_mini | 400 | 模型名 `o4-mini` 不存在 | 修正模型名 |
| github_gpt5 | 400 | 模型名 `gpt-5` 不存在 | 修正模型名 |
| OpenRouter | 429 | 上游临时限流 | 可重试，非永久 |
| nvidia_nemotron | 误判 | 测试脚本解析 bug | 实际可用 ✅ |
| github_gpt4o | 误判 | 测试脚本解析 bug | 实际可用 ✅ |

### 第一梯队：OpenAI 格式 + 确认支持 Tool Call（快速）

| 后端 | 模型 | 延迟 | 代理 | UA |
|------|------|------|------|-----|
| groq_llama70b | Llama-3.3-70B | 524ms | ✅ | ✅ |
| cerebras_gptoss | GPT-OSS-120B | 530ms | ✅ | ✅ |
| cerebras_qwen235b | Qwen-3-235B | 557ms | ✅ | ✅ |
| mistral_large | Mistral-Large | 874ms | ✅ | ✅ |
| mistral_small | Mistral-Small | 973ms | ✅ | ✅ |
| groq_llama4 | Llama-4-Scout | 1089ms | ✅ | ✅ |
| google_flash | Gemini-2.5-Flash | 1626ms | ✅ | ✅ |
| nvidia_qwen_coder | Qwen3-Coder-480B | 2445ms | ❌ | ❌ |
| nvidia_nemotron | Nemotron-49B | ~2000ms | ❌ | ❌ |
| github_gpt4o | GPT-4o | ~2600ms | ✅ | ✅ |

### 第二梯队：Anthropic 原生（兜底，无需格式转换）

| 后端 | 模型 | 延迟 | 代理 | UA |
|------|------|------|------|-----|
| longcat_lite | LongCat-Flash-Lite | ~3000ms | ❌ | ❌ |
| longcat_chat | LongCat-Flash-Chat | ~5000ms | ❌ | ❌ |
| longcat_omni | LongCat-Flash-Omni | ~5000ms | ❌ | ❌ |
| longcat | LongCat-2.0-Preview | ~8000ms | ❌ | ❌ |
| longcat_thinking | LongCat-Flash-Thinking | ~10000ms | ❌ | ❌ |

## 设计方案

### 分层路由策略

```
Claude Code 请求 (带 tools)
    │
    ├─ 第一层：Anthropic 原生透传（5 个 LongCat）
    │   优点：零转换，tool_use 格式完美兼容
    │   缺点：只有 5 个后端，可能慢
    │
    └─ 第二层：OpenAI 格式转换（8+ 个高质量后端）
        优点：速度快（Groq 2s），后端多
        缺点：需要 Anthropic↔OpenAI 格式转换
        已有代码：_convert_tools_anthropic_to_openai()
                  _convert_messages_anthropic_to_openai()
                  _convert_response_openai_to_anthropic()
```

### 选择逻辑

1. P2C 从第一梯队选 1 个 Anthropic 后端
2. 如果失败/超时 → P2C 从第二梯队选 1 个 OpenAI 后端（走格式转换）
3. 最多重试 3 次

### 流式方案

- Claude Code 发 `stream: true` → 使用 `_anthropic_native_stream`
- Anthropic 后端：直接透传 SSE chunks
- OpenAI 后端：逐 chunk 转换格式后透传

### 超时策略

- 第一梯队超时：15s（LongCat 正常 5-8s）
- 第二梯队超时：10s（Groq/GitHub 正常 2-4s）
- 总超时：30s

## 不做的事

- 不缓存 tool 请求（每次上下文不同）
- 不裁剪 tools 列表（后端自己处理）
- 不用付费后端（claude/deepseek_pro/deepseek_flash 排除）

## 验证计划

1. 单元测试：P2C 选择逻辑
2. 集成测试：从服务器 localhost 发带 tools 的请求
3. 端到端：Claude Code 执行 read_file / bash 等 tool call
4. 性能：响应时间从 28s 降到 <10s
