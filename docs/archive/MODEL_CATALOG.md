# LiMa 模型目录 (Model Catalog)

> 267 个后端 · 49 个供应商 · 5 层级 · 6 能力维度
> 最后更新: 2026-06-06
>
> 完整后端配置见 [`backends_registry.py`](../backends_registry.py)

## 总览

| 指标 | 数据 |
|------|------|
| 后端总数 | **267** |
| 供应商数 | **49** (含 18 个免费网关) |
| tool_calls 支持 | **115** 后端 |
| 代码生成 | **code_medium** 33 + **code_floor** 15 |
| 多模态/视觉 | 1 (cf_vision) |

### 供应商分布

| 供应商 | 数量 | 类型 | 模态 |
|--------|:--:|------|------|
| **ModelScope** | **46** | 免费网关 | 文本 · 代码 · 推理 |
| **OpenGateway** | 19 | 免费网关 | 文本 · 代码 · 推理 |
| MiMo | 17 | 免费网关 | 文本 · 代码 · 推理 |
| Cloudflare | 15 | 免费网关 | 文本 · 代码 · 视觉 |
| OpenRouter | 12 | 免费网关 | 文本 · 代码 · 推理 |
| OldLLM (SCNet) | 12 | 逆向网关 | 文本 · 代码 · 推理 |
| GitHub Models | 11 | 免费网关 | 文本 · 代码 · 视觉 |
| NVIDIA NIM | 10 | 免费配额 | 文本 · 代码 |
| Groq | 6 | 免费配额 | 文本 · 代码 |
| LongCat | 6 | 免费无限 | 文本 · 视觉 · 推理 |
| Mistral | 7 | 免费配额 | 文本 · 视觉 · 代码 |
| Cerebras | 3 | 免费配额 | 文本 · 代码 |
| Google Gemini | 4 | 免费配额 | 文本 · 视觉 |
| DeepSeek | stock | 付费 | 文本 · 代码 · 推理 |
| Claude (Anthropic) | stock | 付费 | 文本 · 视觉 · 代码 |
| Agnes AI | 4 | 免费网关 | 文本 · 图像 · 视频 |
| EdgeOne | - | 边缘免费 | 文本 |
| Duck.ai / SAP AI / Groq / ... | ~20 | 混合 | 文本 |

---

## 路由层级

```
L0.5  极速层     Groq/Cerebras/Mistral/GitHub/Google/Cloudflare  (<2s, 有配额)
L1    免费无限   LongCat/中国移动/ModelScope/OpenGateway/Agnes AI  (无限额度)
L2    免费额度   NVIDIA NIM/EdgeOne                                (有额度限制)
L3    免费限量   OpenRouter/OldLLM/MiMo                           (RPM 限制)
L4    付费兜底   DeepSeek/Claude/SCNet                            (按量计费)
```

---

## 免费网关详解

### ModelScope (46 backends)

> API: `api-inference.modelscope.cn` | 免费 · ∞ | 无需审核

| 分类 | 数量 | 代表模型 |
|------|:--:|------|
| **通用池 (general)** | 23 | DeepSeek-V3.2, Qwen3-235B, GLM-5.1, Llama-4, Intern-S2 |
| **编程池 (code_medium)** | 11 | DeepSeek-V3.2, Qwen3-235B, Qwen3-Coder-30B, Qwen3.5-122B |
| **编程池 (code_floor)** | 12 | DeepSeek-R1-0528, Qwen2.5-Coder-32B, Qwen3.5-397B, Llama-4 |

- **tool_calls**: DeepSeek-V3.2, Qwen3-235B, Qwen3-Coder-30B, Qwen3-Next-80B, Qwen3.5-122B, GLM-5.1, Step-3.7-Flash 等
- **推理模型**: DeepSeek-R1-0528, Qwen3-235B-Thinking, Qwen3-Next-80B-Thinking
- **多模态**: ❌ 免费 API 不支持图像输入

### OpenGateway (19 backends)

> API: `api.opengateway.ai` | 免费 · 200 req/day | 无需审核

| 主要模型 | 分类 |
|------|------|
| gpt-5.2, gpt-5.1, gpt-5.0 | code_medium (tool_calls) |
| claude-opus-4.6, claude-sonnet-4.6, claude-haiku-4.6 | code_medium (Anthropic) |
| gemini-3-flash, gemini-3-pro | code_medium |
| deepseek-v4, grok-4.2, llama-4-maverick | code_medium |
| ... | general (7 个) |

### Agnes AI (4 backends)

> API: `apihub.agnes-ai.com` | 免费 · 5 req/min |

| 模型 | 能力 |
|------|------|
| agnes-2.0-flash | 文本 · tool_calls |
| agnes-1.5-flash | 文本 |
| agnes-image-2.x-flash | 多模态 (API 不可用) |

### MiMo (17 backends)

> API: `api.mimo.one` | 免费 · 100 req/day |

Qwen2.5-72B, DeepSeek-V3, GLM-4, MiniMax-M1, 等 — 含 tool_calls 支持。

---

## L0.5 极速层 (20 backends)

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `groq_llama4` | Llama 4 Scout 17B | Groq | 376ms ⚡⚡⚡ | B | Text | 1000 req/5min |
| `cerebras_llama8b` | Llama 3.1 8B | Cerebras | 432ms ⚡⚡⚡ | C | Text | 5 req/min |
| `groq_qwen32b` | Qwen3 32B | Groq | 447ms ⚡⚡⚡ | B+ | Text, Code | 1000 req/5min |
| `groq_gptoss` | GPT-OSS 120B | Groq | 520ms ⚡⚡⚡ | A | Text, Code | 1000 req/5min |
| `mistral_codestral` | Codestral | Mistral | 586ms ⚡⚡⚡ | A | Code | Free quota |
| `mistral_small` | Mistral Small | Mistral | 698ms ⚡⚡⚡ | B | Text | Free quota |
| `groq_llama70b` | Llama 3.3 70B | Groq | 694ms ⚡⚡⚡ | A | Text | 1000 req/5min |
| `mistral_pixtral` | Pixtral Large | Mistral | 796ms ⚡⚡ | A | Vision | Free quota |
| `cf_llama4` | Llama 4 Scout 17B | Cloudflare | 835ms ⚡⚡ | B | Text | 10k neurons/day |
| `cf_vision` | Llama 3.2 11B Vision | Cloudflare | 867ms ⚡⚡ | B | Vision | 10k neurons/day |
| `mistral_medium` | Mistral Medium | Mistral | 979ms ⚡⚡ | A | Text | Free quota |
| `google_flash_lite` | Gemini 3.1 Flash Lite | Google | 1.1s ⚡⚡ | B | Vision | 15 RPM |
| `cf_mistral` | Mistral Small 3.1 24B | Cloudflare | 1.1s ⚡⚡ | B | Text | 10k neurons/day |
| `cf_qwen_coder` | Qwen 2.5 Coder 32B | Cloudflare | 1.3s ⚡⚡ | B+ | Code | 10k neurons/day |
| `google_flash` | Gemini 2.5 Flash | Google | 1.5s ⚡⚡ | A | Vision | 15 RPM |
| `cerebras_qwen235b` | Qwen3 235B | Cerebras | 1.9s ⚡⚡ | S | Text | 5 req/min |
| `cf_llama70b` | Llama 3.3 70B FP8 | Cloudflare | 2.1s ⚡ | A | Text | 10k neurons/day |
| `github_gpt4o` | GPT-4o | GitHub | 2.2s ⚡ | S | Vision, Code | 20000 req/min |
| `github_gpt4o_mini` | GPT-4o-mini | GitHub | 3.0s ⚡ | B+ | Vision | 20000 req/min |
| `github_llama70b` | Llama 3.3 70B | GitHub | 2.1s ⚡ | A | Text | 20000 req/min |

### L1 免费无限层 (8 + 69 免费网关 = 77 backends)

> 上方「免费网关详解」中的 ModelScope(46)、OpenGateway(19)、Agnes AI(4) 均属 L1。
> 以下是传统 L1 后端：

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `unclose_hermes` | Hermes 3 (Llama 3.1 8B) | UncloseAI | 1.4s ⚡⚡ | C | Text | ∞ 无需Key |
| `unclose_qwen` | Qwen 3.6 27B | UncloseAI | 3.0s ⚡ | B | Text, Code | ∞ 无需Key |
| `longcat_lite` | LongCat-Flash-Lite | LongCat | ~2s ⚡ | B | Text | ∞ |
| `longcat_chat` | LongCat-Flash-Chat | LongCat | ~2s ⚡ | B+ | Text | ∞ |
| `longcat` | LongCat-2.0-Preview | LongCat | ~5s 🐢 | A | Text | ∞ |
| `longcat_thinking` | LongCat-Flash-Thinking | LongCat | ~8s 🐢 | A | Reasoning | ∞ |
| `longcat_omni` | LongCat-Flash-Omni | LongCat | ~5s 🐢 | A | Vision | ∞ |
| `chinamobile` | MiniMax M25 | 中国移动 | ~3s ⚡ | B+ | Text | ∞ |

### L2 免费额度层 — Nvidia NIM (6 backends)

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `nvidia_phi4` | Phi-4 Mini | Nvidia | 1-2s ⚡⚡ | C | Text | Free quota |
| `nvidia_llama4` | Llama 4 Maverick 17B | Nvidia | 8-12s 🐢 | B | Text | Free quota |
| `nvidia_nemotron` | Nemotron Super 49B | Nvidia | 8-12s 🐢 | A | Text | Free quota |
| `nvidia_llama70b` | Llama 3.3 70B | Nvidia | 8-12s 🐢 | A | Text | Free quota |
| `nvidia_qwen_coder` | Qwen3 Coder 480B | Nvidia | 8-12s 🐢 | S | Code | Free quota |
| `nvidia_mistral` | Mistral Large 675B | Nvidia | 8-12s 🐢 | S | Text | Free quota |

### L3 免费限量层 — OpenRouter (5 backends)

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `or_deepseek_r1` | DeepSeek V4 Flash | OpenRouter | 10-60s 🐢 | A | Reasoning | 20 RPM/200 RPD |
| `or_qwen3_coder` | Qwen3 Coder | OpenRouter | 10-60s 🐢 | A | Code | 20 RPM/200 RPD |
| `or_llama70b` | Llama 3.3 70B | OpenRouter | 10-60s 🐢 | A | Text | 20 RPM/200 RPD |
| `or_nemotron` | Nemotron Super 49B | OpenRouter | 10-60s 🐢 | A | Text | 20 RPM/200 RPD |
| `or_qwen3_80b` | Qwen3 Next 80B | OpenRouter | 10-60s 🐢 | A | Text | 20 RPM/200 RPD |

### L4 付费兜底层 (3 backends)

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `deepseek_flash` | DeepSeek V4 Flash | DeepSeek | ~3s ⚡ | A | Text, Code | Paid |
| `deepseek_pro` | DeepSeek V4 Pro | DeepSeek | ~5s 🐢 | S | Reasoning | Paid |
| `claude` | Claude Sonnet 4.6 | Anthropic | ~4s ⚡ | S | Vision, Code | Paid |

### 本地层 (1 backend)

| ID | 模型 | 供应商 | 延迟 | Quality | Modality | 限制 |
|---|---|---|---|---|---|---|
| `local` | LM Studio | Local | Variable | - | Text | ∞ Zero cost |

---

## 能力矩阵

### 按能力分组

| 能力 | 后端列表 | 推荐首选 |
|------|----------|----------|
| **代码生成** | groq_gptoss, groq_qwen32b, nvidia_qwen_coder, mistral_codestral, cf_qwen_coder, or_qwen3_coder, github_gpt4o, deepseek_flash, claude | groq_gptoss (520ms) |
| **视觉/多模态** | cf_vision, mistral_pixtral, github_gpt4o, google_flash, google_flash_lite, longcat_omni, claude | cf_vision (867ms) |
| **深度推理** | or_deepseek_r1, longcat_thinking, deepseek_pro, claude | longcat_thinking (免费) |
| **通用对话** | groq_llama4/70b, unclose_hermes, longcat_lite/chat, chinamobile | groq_llama4 (376ms) |
| **嵌入式/硬件** | nvidia_nemotron, groq_llama70b, longcat_thinking | nvidia_nemotron |

### 按速度分组

| 速度档 | 后端数 | 代表 |
|--------|--------|------|
| ⚡⚡⚡ <700ms | 7 | Groq 全系, Mistral Codestral/Small |
| ⚡⚡ 700ms-2s | 10 | Mistral Pixtral, CF 全系, Google Flash Lite, Nvidia Phi4 |
| ⚡ 2-5s | 10 | GitHub, UncloseAI, LongCat Lite/Chat, DeepSeek Flash |
| 🐢 >5s | 16 | Nvidia NIM, OpenRouter, LongCat Thinking, DeepSeek Pro |

---

## 供应商总览

| 供应商 | 后端数 | 最快 | 多模态 | 限制 | 可靠性 |
|--------|--------|------|--------|------|--------|
| Groq | 4 | 376ms | ❌ | 1000 req/5min | High |
| Mistral | 4 | 586ms | ✅ Pixtral | Free quota | High |
| Cloudflare | 5 | 835ms | ✅ Vision | 10k neurons/day | High |
| Google | 2 | 1.1s | ✅ | 15 RPM | High |
| Cerebras | 2 | 432ms | ❌ | 5 req/min | Medium |
| GitHub | 3 | 2.1s | ✅ GPT-4o | 20000 req/min | High |
| UncloseAI | 2 | 1.4s | ❌ | ∞ | Low |
| LongCat | 5 | ~2s | ✅ Omni | ∞ | Medium |
| NVIDIA NIM | 10 | 1-2s ~ 8-12s | ❌ | Free quota | Medium |
| OpenRouter | 12 | 10-60s | ❌ | 20 RPM/200 RPD | Low |
| **ModelScope** | **46** | 3-90s | ❌ | ∞ | Medium |
| **OpenGateway** | **19** | 3-30s | ❌ | 200 req/day | Medium |
| MiMo | 17 | 2-10s | ❌ | 100 req/day | Medium |
| OldLLM/SCNet | 12 | 5-30s | ❌ | Rate limited | Low |
| Agnes AI | 4 | 2-5s | ❌ | 5 req/min | Medium |
| DeepSeek | stock | ~3s | ❌ | Paid | High |
| Anthropic | 1 | ~4s | ✅ | Paid | High |
| 中国移动 | 1 | ~3s | ❌ | ∞ | Medium |
| Local | 1 | Var | ❌ | ∞ | High |

---

## 路由推荐策略

基于 RouteLLM 的 strong/weak 二分法 + Portkey 的条件路由，推荐：

```
Intent 确定 → 按 Fallback Chain 走（已有）
Intent 不确定 → 默认走 groq_llama4 (376ms, 通用, 高可靠)
需要深度推理 → longcat_thinking (免费∞) 或 or_deepseek_r1
需要代码 → groq_gptoss (520ms, 120B) 或 nvidia_qwen_coder (480B)
需要视觉 → cf_vision (867ms) → mistral_pixtral → github_gpt4o
```

## 环境变量

```bash
GROQ_API_KEY              # Groq (4 backends)
CEREBRAS_API_KEY          # Cerebras (2 backends)
GITHUB_TOKEN              # GitHub Models (3 backends)
GOOGLE_AI_KEY             # Google Gemini (2 backends)
CLOUDFLARE_TOKEN          # Cloudflare Workers AI (5 backends)
CLOUDFLARE_ACCOUNT_ID     # Cloudflare account ID
MISTRAL_API_KEY           # Mistral (4 backends)
NVIDIA_API_KEY            # Nvidia NIM (6 backends)
OPENROUTER_API_KEY        # OpenRouter (5 backends)
LONGCAT_API_KEY           # LongCat (5 backends)
DEEPSEEK_API_KEY          # DeepSeek (2 backends)
CLAUDE_API_KEY            # Claude (1 backend)
CHINAMOBILE_API_KEY       # China Mobile (1 backend)
```
