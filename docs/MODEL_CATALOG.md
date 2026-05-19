# LiMa 模型目录 (Model Catalog)

> 43 个后端 · 14 个供应商 · 5 层级 · 6 能力维度

## 分类维度

参考 LiteLLM / Portkey / RouteLLM / WallasAPI 的行业实践，采用 6 维分类：

| 维度 | 值域 | 说明 |
|------|------|------|
| **Speed** | ⚡⚡⚡ (<700ms) / ⚡⚡ (700ms-2s) / ⚡ (2-5s) / 🐢 (>5s) | 首 token 延迟 |
| **Quality** | S / A / B / C | 综合输出质量 (S=GPT-4o级, A=70B级, B=30B级, C=8B级) |
| **Cost** | Free∞ / Free-Quota / Paid | 计费模式 |
| **Modality** | Text / Vision / Audio / Code / Reasoning | 能力标签 |
| **Tier** | L0.5 / L1 / L2 / L3 / L4 | 路由优先级层级 |
| **Reliability** | High / Medium / Low | 可用性 (基于熔断器历史) |

## 层级定义

```
L0.5  极速层    Groq/Cerebras/Mistral/GitHub/Google/Cloudflare  (<2s, 有额度)
L1    免费无限  UncloseAI/LongCat/中国移动                      (无限额度)
L2    免费额度  Nvidia NIM                                      (有额度限制)
L3    免费限量  OpenRouter                                      (20 RPM / 200 RPD)
L4    付费兜底  DeepSeek/Claude                                 (按量计费)
```

---

## 完整模型清单

### L0.5 极速层 (20 backends)

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

### L1 免费无限层 (8 backends)

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
| Nvidia | 6 | 1-2s | ❌ | Free quota | Medium |
| OpenRouter | 5 | 10-60s | ❌ | 20 RPM/200 RPD | Low |
| DeepSeek | 2 | ~3s | ❌ | Paid | High |
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
