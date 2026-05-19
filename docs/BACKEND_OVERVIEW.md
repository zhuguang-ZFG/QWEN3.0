# LiMa 免费 AI 后端资源总览

> 最后更新：2026-05-19

## 后端层级体系

```
L0.5 极速层 — Groq + Cerebras (正规公司免费额度)
L1   免费无限层 — UncloseAI (无需 Key, 无限额度)
L2   免费额度层 — Nvidia NIM (免费额度, 需 Key)
L3   免费额度层 — OpenRouter (20 RPM / 200 RPD)
L4   付费兜底 — DeepSeek / Claude
```

## 已集成后端

### L0.5 极速层

| 后端 | 模型 | 延迟 | 速度 | 限制 | 状态 |
|------|------|------|------|------|------|
| `groq_llama4` | Llama 4 Scout 17B | **376ms** | 48 tok/s | 1000 req/5min | ✅ |
| `groq_qwen32b` | Qwen3 32B | **447ms** | 134 tok/s | 同上 | ✅ |
| `groq_gptoss` | GPT-OSS 120B | **520ms** | 145 tok/s | 同上 | ✅ |
| `groq_llama70b` | Llama 3.3 70B | **694ms** | 49 tok/s | 同上 | ✅ |
| `cerebras_qwen235b` | Qwen3 235B | **1.9s** | 35 tok/s | 5 req/min | ✅ |
| `cerebras_llama8b` | Llama 3.1 8B | **432ms** | 37 tok/s | 同上 | ✅ |

### L1 免费无限层

| 后端 | 模型 | 延迟 | 限制 | 状态 |
|------|------|------|------|------|
| `unclose_hermes` | Hermes 3 (Llama 3.1 8B) | 1.4s | 无限 | ✅ |
| `unclose_qwen` | Qwen 3.6 27B | 3.0s | 无限 | ✅ |

### L2 免费额度层 (Nvidia NIM)

| 后端 | 模型 | 状态 |
|------|------|------|
| `nvidia_qwen_coder` | Qwen3 Coder 480B | ✅ |
| `nvidia_llama70b` | Llama 3.3 70B | ✅ |
| `nvidia_nemotron` | Nemotron Super 49B | ✅ |
| `nvidia_llama4` | Llama 4 Maverick 17B | ✅ |
| `nvidia_mistral` | Mistral Large 675B | ✅ |
| `nvidia_phi4` | Phi-4 Mini | ✅ |

### L3 免费额度层 (OpenRouter, 20 RPM / 200 RPD)

| 后端 | 模型 | 状态 |
|------|------|------|
| `or_deepseek_r1` | DeepSeek V4 Flash | ✅ |
| `or_qwen3_coder` | Qwen3 Coder | ✅ |
| `or_llama70b` | Llama 3.3 70B | ✅ |
| `or_nemotron` | Nemotron Super 49B | ✅ |
| `or_qwen3_80b` | Qwen3 Next 80B | ✅ |

### L4 付费兜底

| 后端 | 模型 | 状态 |
|------|------|------|
| `deepseek_pro` | DeepSeek V4 Pro | ✅ |
| `deepseek_flash` | DeepSeek V4 Flash | ✅ |
| `claude` | Claude Sonnet 4.6 | ✅ |

### 其他

| 后端 | 用途 | 状态 |
|------|------|------|
| `longcat` 系列 (5 个) | LongCat 免费对话/推理 | ✅ |
| `chinamobile` | 中国移动 MiniMax M25 | ✅ |
| `local` | 本地 LM Studio | ✅ |

## 性能排名 (首 token 延迟)

```
  1. groq_llama4       376ms  ⚡⚡⚡
  2. cerebras_llama8b  432ms  ⚡⚡⚡
  3. groq_qwen32b      447ms  ⚡⚡⚡
  4. groq_gptoss       520ms  ⚡⚡⚡
  5. groq_llama70b     694ms  ⚡⚡
  6. unclose_hermes    1400ms ⚡
  7. cerebras_qwen235b 1900ms ⚡
  8. unclose_qwen      3000ms
  9. nvidia_*          8-12s
 10. or_*              10-60s
```

## 调研过但未集成

| 服务 | 原因 |
|------|------|
| Puter.com | 仅浏览器 SDK，无服务端 API |
| OllamaFreeAPI | 社区节点不稳定，50% 离线 |
| Pollinations / llm7.io / g4f.dev | Cloudflare 403 拦截 |
| FreeTheAI | 待 Discord Key（方案已写） |

## 待办事项

| 优先级 | 行动 | 预期收益 | 状态 |
|--------|------|----------|------|
| ~~P0~~ | ~~注册 Groq 免费 Key~~ | ~~70B 模型 + 极速推理~~ | ✅ 已集成 |
| ~~P0~~ | ~~注册 Cerebras 免费 Key~~ | ~~235B 模型（最强免费）~~ | ✅ 已集成 |
| ~~P1~~ | ~~注册 GitHub Models~~ | ~~GPT-4o 免费访问~~ | ✅ 已集成 |
| ~~P2~~ | ~~测试 sixfinger-api~~ | ~~无需 Key 的备选~~ | ❌ 已下线 (404) |
| P3 | 自建 gpt4free | 66k stars 但维护成本高 | 待评估 |
| P3 | 注册 FreeTheAI Discord Key | 16k 模型 + 图片生成 | 待执行 |

## 路由策略

投机调用默认: `groq_llama4` (376ms)
默认 fallback: `groq_llama70b → unclose_hermes → nvidia_llama70b → longcat → claude`

各意图首选:
- trivial: groq_llama4
- code_generation: groq_gptoss → nvidia_qwen_coder
- architecture: groq_gptoss → cerebras_qwen235b
- general_cnc: groq_llama4 → unclose_hermes
- cnc_trouble: groq_llama70b → unclose_hermes
