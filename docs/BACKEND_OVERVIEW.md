# LiMa 免费 AI 后端资源总览

> 最后更新：2026-05-20
> 后端总数：79 个 / 24 个供应商

## 后端层级体系

```
L0.5 极速层 — Groq + Cerebras + Mistral + GitHub + Google + Cloudflare
L1   免费无限层 — UncloseAI (无需 Key, 无限额度)
L2   免费额度层 — Nvidia NIM (免费额度, 需 Key)
L3   免费额度层 — OpenRouter (20 RPM / 200 RPD)
L4   付费兜底 — DeepSeek / Claude
```

## 已集成后端 (74 个, 21 个供应商)

### L0.5 极速层

| 后端 | 模型 | 延迟 | 速度 | 限制 | 状态 |
|------|------|------|------|------|------|
| `groq_llama4` | Llama 4 Scout 17B | **376ms** | 48 tok/s | 1000 req/5min | ✅ |
| `groq_qwen32b` | Qwen3 32B | **447ms** | 134 tok/s | 同上 | ✅ |
| `groq_gptoss` | GPT-OSS 120B | **520ms** | 145 tok/s | 同上 | ✅ |
| `mistral_codestral` | Codestral | **586ms** | - | 免费额度 | ✅ |
| `mistral_small` | Mistral Small | **698ms** | - | 免费额度 | ✅ |
| `groq_llama70b` | Llama 3.3 70B | **694ms** | 49 tok/s | 1000 req/5min | ✅ |
| `mistral_pixtral` | Pixtral Large (视觉) | **796ms** | - | 免费额度 | ✅ |
| `cf_llama4` | Llama 4 Scout 17B | **835ms** | - | 10k neurons/day | ✅ |
| `cf_vision` | Llama 3.2 11B Vision | **867ms** | - | 同上 | ✅ |
| `mistral_medium` | Mistral Medium | **979ms** | - | 免费额度 | ✅ |
| `google_flash_lite` | Gemini 3.1 Flash Lite | **1.1s** | - | 15 RPM | ✅ |
| `cf_mistral` | Mistral Small 3.1 24B | **1.1s** | - | 10k neurons/day | ✅ |
| `cf_qwen_coder` | Qwen 2.5 Coder 32B | **1.3s** | - | 同上 | ✅ |
| `google_flash` | Gemini 2.5 Flash | **1.5s** | - | 15 RPM | ✅ |
| `cerebras_qwen235b` | Qwen3 235B | **1.9s** | 35 tok/s | 5 req/min | ✅ |
| `cf_llama70b` | Llama 3.3 70B FP8 | **2.1s** | - | 10k neurons/day | ✅ |
| `github_gpt4o` | GPT-4o (视觉) | **2.2s** | - | 20000 req/min | ✅ |
| `github_gpt4o_mini` | GPT-4o-mini | **3.0s** | - | 同上 | ✅ |
| `github_llama70b` | Llama 3.3 70B | **2.1s** | - | 同上 | ✅ |
| `cerebras_llama8b` | Llama 3.1 8B | **432ms** | 37 tok/s | 5 req/min | ✅ |

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

## 多模态视觉路由

自动检测消息中的 `image_url` → 切换 vision chain:

```
cf_vision (867ms) → mistral_pixtral (796ms) → github_gpt4o (4.6s) → google_flash → google_flash_lite
```

| 后端 | 模型 | 延迟 | 备注 |
|------|------|------|------|
| `cf_vision` | Llama 3.2 11B Vision | 867ms | 原生 /ai/run/ 端点 |
| `mistral_pixtral` | Pixtral Large | 796ms | OpenAI 兼容 |
| `github_gpt4o` | GPT-4o | 4.6s | 最强视觉 |
| `google_flash` | Gemini 2.5 Flash | 1.5s | 快速视觉 |
| `google_flash_lite` | Gemini 3.1 Flash Lite | 11s | 兜底 |

## 性能排名 (首 token 延迟)

```
  1. groq_llama4       376ms  ⚡⚡⚡
  2. cerebras_llama8b  432ms  ⚡⚡⚡
  3. groq_qwen32b      447ms  ⚡⚡⚡
  4. groq_gptoss       520ms  ⚡⚡⚡
  5. mistral_codestral 586ms  ⚡⚡
  6. groq_llama70b     694ms  ⚡⚡
  7. mistral_pixtral   796ms  ⚡⚡ (视觉)
  8. cf_llama4         835ms  ⚡⚡
  9. cf_vision         867ms  ⚡⚡ (视觉)
 10. google_flash_lite 1100ms ⚡
 11. unclose_hermes    1400ms ⚡
 12. cerebras_qwen235b 1900ms ⚡
 13. github_gpt4o      2200ms (视觉)
 14. unclose_qwen      3000ms
 15. nvidia_*          8-12s
 16. or_*              10-60s
```

## 供应商汇总

| 供应商 | 后端数 | 最快延迟 | 限制 | 多模态 |
|--------|--------|----------|------|--------|
| 国内直连 | 11 | <100ms | 无限 | ✅ 部分 |
| Groq | 6 | 376ms | 1000 req/5min | ❌ |
| GitHub | 8 | 2.1s | 20000 req/min | ✅ GPT-4o |
| NVIDIA | 6 | 8-12s | 免费额度 | ❌ |
| OpenRouter | 10 | 10-60s | 20 RPM | ❌ |
| Cerebras | 3 | 432ms | 5 req/min | ❌ |
| Mistral | 6 | 586ms | 免费额度 | ✅ Pixtral |
| Cloudflare | 5 | 835ms | 10k neurons/day | ✅ Vision |
| Google | 4 | 1.1s | 15 RPM | ✅ |
| LongCat | 5 | 5-8s | 免费 | ❌ |
| UncloseAI | 2 | 1.4s | 无限 | ❌ |
| DeepSeek | 2 | <500ms | 付费 | ❌ |
| 其他 | 6 | 1-3s | 免费 | ❌ |

## 调研过但未集成

| 服务 | 原因 |
|------|------|
| Puter.com | 仅浏览器 SDK，无服务端 API |
| OllamaFreeAPI | 社区节点不稳定，50% 离线 |
| Pollinations.ai | 旧 API 废弃，新 API 需注册，15s/req 限制 |
| llm7.io / g4f.dev | Cloudflare 403 拦截 |
| FreeTheAI | 待 Discord Key（方案已写） |
| sixfinger-api | 已下线 (404) |

## 待办事项

| 优先级 | 行动 | 预期收益 | 状态 |
|--------|------|----------|------|
| ~~P0~~ | ~~注册 Groq 免费 Key~~ | ~~70B 模型 + 极速推理~~ | ✅ 已集成 |
| ~~P0~~ | ~~注册 Cerebras 免费 Key~~ | ~~235B 模型（最强免费）~~ | ✅ 已集成 |
| ~~P1~~ | ~~注册 GitHub Models~~ | ~~GPT-4o 免费访问~~ | ✅ 已集成 |
| ~~P2~~ | ~~测试 sixfinger-api~~ | ~~无需 Key 的备选~~ | ❌ 已下线 (404) |
| P3 | 自建 gpt4free | 66k stars 但维护成本高 | 待评估 |
| P3 | 注册 FreeTheAI Discord Key | 16k 模型 + 图片生成 | 待执行 |

## 环境变量

```bash
GROQ_API_KEY=gsk_...              # Groq 极速推理
CEREBRAS_API_KEY=csk-...          # Cerebras 超大模型
GITHUB_TOKEN=gho_...              # GitHub Models
GOOGLE_AI_KEY=AIza...             # Google Gemini
CLOUDFLARE_TOKEN=cfut_...         # Cloudflare Workers AI
CLOUDFLARE_ACCOUNT_ID=...         # Cloudflare 账号 ID
MISTRAL_API_KEY=...               # Mistral
NVIDIA_API_KEY=nvapi-...          # Nvidia NIM
OPENROUTER_API_KEY=sk-or-...      # OpenRouter
LONGCAT_API_KEY=ak_...            # LongCat
DEEPSEEK_API_KEY=sk-...           # DeepSeek 付费
CLAUDE_API_KEY=sk-...             # Claude 付费
CHINAMOBILE_API_KEY=sk-...        # 中国移动
```

## 路由策略

投机调用默认: `groq_llama4` (376ms)
默认 fallback: `groq_llama70b → unclose_hermes → nvidia_llama70b → longcat → claude`

各意图首选:
- trivial: groq_llama4
- code_generation: groq_gptoss → nvidia_qwen_coder → groq_qwen32b
- architecture: groq_gptoss → cerebras_qwen235b → github_gpt4o
- general_cnc: groq_llama4 → unclose_hermes
- cnc_trouble: groq_llama70b → unclose_hermes
- vision: cf_vision → mistral_pixtral → github_gpt4o → google_flash
