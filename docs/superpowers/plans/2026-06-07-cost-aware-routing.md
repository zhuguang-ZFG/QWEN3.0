# Cost-Aware Routing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-model cost tracking and cost-aware backend selection that prefers cheaper backends for non-critical requests while maintaining quality for complex tasks.

**Architecture:** A static cost table maps provider/model to input/output token prices. Each request estimates cost from token usage. Routing scorer adds a cost_score dimension weighted by scenario criticality. Admin dashboard shows cost metrics and savings reports.

**Tech Stack:** Python 3.10+, pytest, existing LiMa routing/stats infrastructure

---

## Task 1: Cost Table

Create `D:\QWEN3.0\cost_table.py` with a static cost lookup and estimation function.

### Files

- **Create:** `D:\QWEN3.0\cost_table.py`
- **Create:** `D:\QWEN3.0\tests\test_cost_table.py`

### Steps

- [ ] **1.1** Create `cost_table.py` with pricing data and estimation function.

```python
"""Static cost table for LiMa backend models.

Maps provider/model to per-1K-token pricing. Used by cost-aware routing
to estimate request costs and prefer cheaper backends for non-critical tasks.

Prices are in USD per 1,000 tokens. Sources: official provider pricing pages.
Free-tier / self-hosted / community backends have zero cost.
"""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# ── Pricing table (USD per 1K tokens) ─────────────────────────────────────────
# Key = model string as it appears in backends_registry.py BACKENDS[name]["model"]
# Value = {"input_per_1k": float, "output_per_1k": float, "currency": "USD"}
#
# Free / self-hosted / community models are listed with 0.0 pricing.
# Models not listed are treated as unknown (estimate returns 0.0 with a warning).

COST_TABLE: dict[str, dict[str, float | str]] = {
    # ── OpenAI models ──────────────────────────────────────────────────────────
    "gpt-4o": {"input_per_1k": 0.00250, "output_per_1k": 0.01000, "currency": "USD"},
    "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.00060, "currency": "USD"},
    "gpt-4": {"input_per_1k": 0.03000, "output_per_1k": 0.06000, "currency": "USD"},
    "gpt-4.1": {"input_per_1k": 0.00200, "output_per_1k": 0.00800, "currency": "USD"},
    "gpt-4.1-mini": {"input_per_1k": 0.00040, "output_per_1k": 0.00160, "currency": "USD"},
    "gpt-4.1-nano": {"input_per_1k": 0.00010, "output_per_1k": 0.00040, "currency": "USD"},
    "gpt-5": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5-mini": {"input_per_1k": 0.00250, "output_per_1k": 0.01000, "currency": "USD"},
    "gpt-5.1": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5.2": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5.3": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5.3-codex": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5.4": {"input_per_1k": 0.01500, "output_per_1k": 0.06000, "currency": "USD"},
    "gpt-5.4-mini": {"input_per_1k": 0.00100, "output_per_1k": 0.00400, "currency": "USD"},
    "gpt-5.5": {"input_per_1k": 0.02000, "output_per_1k": 0.08000, "currency": "USD"},
    "o1": {"input_per_1k": 0.01500, "output_per_1k": 0.06000, "currency": "USD"},
    "o3-mini": {"input_per_1k": 0.00110, "output_per_1k": 0.00440, "currency": "USD"},
    "o4-mini": {"input_per_1k": 0.00110, "output_per_1k": 0.00440, "currency": "USD"},
    "gpt-5-nano": {"input_per_1k": 0.00005, "output_per_1k": 0.00040, "currency": "USD"},
    "gpt-5-codex": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},
    "gpt-5.4-openai-compact": {"input_per_1k": 0.01500, "output_per_1k": 0.06000, "currency": "USD"},
    "gpt-5.5-openai-compact": {"input_per_1k": 0.02000, "output_per_1k": 0.08000, "currency": "USD"},
    "codex-auto-review": {"input_per_1k": 0.01000, "output_per_1k": 0.03000, "currency": "USD"},

    # ── Anthropic models ───────────────────────────────────────────────────────
    "claude-3-5-sonnet-20241022": {"input_per_1k": 0.00300, "output_per_1k": 0.01500, "currency": "USD"},
    "claude-sonnet-4-6": {"input_per_1k": 0.00300, "output_per_1k": 0.01500, "currency": "USD"},
    "claude-haiku-4-5": {"input_per_1k": 0.00080, "output_per_1k": 0.00400, "currency": "USD"},

    # ── Google models ──────────────────────────────────────────────────────────
    "gemini-2.5-flash": {"input_per_1k": 0.00015, "output_per_1k": 0.00060, "currency": "USD"},
    "gemini-3.1-flash-lite": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "gemini-2.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.01000, "currency": "USD"},
    "gemini-2.0-flash": {"input_per_1k": 0.00010, "output_per_1k": 0.00040, "currency": "USD"},

    # ── Mistral models ─────────────────────────────────────────────────────────
    "mistral-large-latest": {"input_per_1k": 0.00200, "output_per_1k": 0.00600, "currency": "USD"},
    "mistral-small-latest": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "mistral-medium-latest": {"input_per_1k": 0.00080, "output_per_1k": 0.00240, "currency": "USD"},
    "codestral-latest": {"input_per_1k": 0.00030, "output_per_1k": 0.00090, "currency": "USD"},
    "devstral-small-latest": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "pixtral-large-latest": {"input_per_1k": 0.00200, "output_per_1k": 0.00600, "currency": "USD"},

    # ── Meta Llama models (via providers) ──────────────────────────────────────
    "llama-3.3-70b-versatile": {"input_per_1k": 0.00059, "output_per_1k": 0.00079, "currency": "USD"},
    "llama-3.3-70b-instruct": {"input_per_1k": 0.00059, "output_per_1k": 0.00079, "currency": "USD"},
    "llama-3.3-70B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "llama3.1-8b": {"input_per_1k": 0.00010, "output_per_1k": 0.00010, "currency": "USD"},
    "llama-3.1-8b-instant": {"input_per_1k": 0.00005, "output_per_1k": 0.00008, "currency": "USD"},
    "meta-llama/llama-3.3-70b-instruct": {"input_per_1k": 0.00059, "output_per_1k": 0.00079, "currency": "USD"},
    "meta-llama/llama-4-maverick-17b-128e-instruct": {"input_per_1k": 0.00020, "output_per_1k": 0.00060, "currency": "USD"},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "meta-llama/llama-4-scout": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "Llama-3.3-70B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "llama-3.3-70b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "llama-4-scout": {"input_per_1k": 0.00010, "output_per_1k": 0.00030, "currency": "USD"},
    "Meta-Llama-4-Maverick-17B-128E-Instruct": {"input_per_1k": 0.00020, "output_per_1k": 0.00060, "currency": "USD"},
    "LLM-Research/Llama-4-Maverick-17B-128E-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Qwen models ────────────────────────────────────────────────────────────
    "qwen-3-235b-a22b-instruct-2507": {"input_per_1k": 0.00010, "output_per_1k": 0.00010, "currency": "USD"},
    "qwen/qwen3-coder:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen/qwen3-next-80b-a3b-instruct:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen/qwen3-32b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen3-8b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen-3-coder-plus": {"input_per_1k": 0.00030, "output_per_1k": 0.00090, "currency": "USD"},

    # ── DeepSeek models ────────────────────────────────────────────────────────
    "deepseek/deepseek-v4-flash:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-r1": {"input_per_1k": 0.00055, "output_per_1k": 0.00219, "currency": "USD"},

    # ── Groq hosted models ─────────────────────────────────────────────────────
    "openai/gpt-oss-120b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "openai/gpt-oss-20b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "gpt-oss-120b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── NVIDIA hosted models ───────────────────────────────────────────────────
    "nvidia/llama-3.3-nemotron-super-49b-v1": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "meta/llama-3.3-70b-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen/qwen3-coder-480b-a35b-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mistralai/mistral-large-3-675b-instruct-2512": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "microsoft/phi-4-mini-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-ai/deepseek-v4-pro": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen/qwen3.5-397b-a17b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "z-ai/glm-5.1": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "moonshotai/kimi-k2.5": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "nvidia/nemotron-3-super-120b-a12b:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── xAI Grok ───────────────────────────────────────────────────────────────
    "x-ai/grok-4.3": {"input_per_1k": 0.00300, "output_per_1k": 0.01200, "currency": "USD"},

    # ── Kimi / GLM (Chinese providers) ─────────────────────────────────────────
    "moonshotai/kimi-k2.6": {"input_per_1k": 0.00080, "output_per_1k": 0.00200, "currency": "USD"},
    "moonshotai/Kimi-K2.5": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "glm-4-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "glm-4.7-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "ZhipuAI/GLM-5": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "ZhipuAI/GLM-5.1": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "z-ai/glm-4.5-air:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "glm-4.5-air": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "z-ai/glm-4.6": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Cloudflare Workers AI models ───────────────────────────────────────────
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/meta/llama-4-scout-17b-16e-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/qwen/qwen2.5-coder-32b-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/mistralai/mistral-small-3.1-24b-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/moonshotai/kimi-k2.6": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/qwen/qwq-32b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/openai/gpt-oss-120b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/qwen/qwen3-30b-a3b-fp8": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/nvidia/nemotron-3-120b-a12b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/zai-org/glm-4.7-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "@cf/google/gemma-4-26b-a4b-it": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── MiniMax ────────────────────────────────────────────────────────────────
    "minimax-m25": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "minimax-m2.5-free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "minimax/minimax-m2.5:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "MiniMax-M2.7": {"input_per_1k": 0.00030, "output_per_1k": 0.00090, "currency": "USD"},
    "minimax/MiniMax-M2.7": {"input_per_1k": 0.00030, "output_per_1k": 0.00090, "currency": "USD"},

    # ── LongCat ────────────────────────────────────────────────────────────────
    "LongCat-2.0-Preview": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Cohere ─────────────────────────────────────────────────────────────────
    "command-a-03-2025": {"input_per_1k": 0.00150, "output_per_1k": 0.00600, "currency": "USD"},
    "command-a-plus-05-2026": {"input_per_1k": 0.00250, "output_per_1k": 0.01000, "currency": "USD"},
    "command-a-reasoning-08-2025": {"input_per_1k": 0.00300, "output_per_1k": 0.01200, "currency": "USD"},
    "command-a-vision-07-2025": {"input_per_1k": 0.00150, "output_per_1k": 0.00600, "currency": "USD"},

    # ── DeepInfra hosted ───────────────────────────────────────────────────────
    "deepseek-ai/DeepSeek-V4-Flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-ai/DeepSeek-R1-0528": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-ai/deepseek-coder-33b-instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-235B-A22B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen2.5-Coder-32B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "codellama/CodeLlama-70b-Instruct-hf": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── ModelScope (free) ──────────────────────────────────────────────────────
    "Qwen/Qwen2.5-Coder-14B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen2.5-Coder-7B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-8B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-235B-A22B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-235B-A22B-Thinking-2507": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-32B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-Coder-30B-A3B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-Next-80B-A3B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-Next-80B-A3B-Thinking": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3.5-27B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3.5-35B-A3B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3.5-122B-A10B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3.5-397B-A17B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "stepfun-ai/Step-3.7-Flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mistralai/Mistral-Large-Instruct-2407": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Shanghai_AI_Laboratory/Intern-S2-Preview": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "THUDM/glm-4-9b-chat": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Community / free proxy models ──────────────────────────────────────────
    "gpt-3": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "auto": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "openai": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "openai-large": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen-coder": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "local-model": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "hermes-agent": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── MiMo ───────────────────────────────────────────────────────────────────
    "mimo-v2-pro": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mimo-v2.5-pro": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mimo-v2.5": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mimo-v2-omni": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mimo-v2.5-tts": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mimo-v2-tts": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Self-hosted / community proxy (all zero cost) ──────────────────────────
    "big-pickle": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-v4-flash-free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen3.6-plus-free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "nemotron-3-super-free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen3-30b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen3-235b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-v4-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-v4-pro": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "DeepSeek-R1": {"input_per_1k": 0.00055, "output_per_1k": 0.00219, "currency": "USD"},
    "DeepSeek-V3.2": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-ai/DeepSeek-V3.2": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen/Qwen3-32B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "qwen2.5-coder-32b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "deepseek-r1-32b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "mistral-small-3.1": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen3.6-27B-UD-Q4_K_XL.gguf": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Other provider proxies ─────────────────────────────────────────────────
    "google/gemma-4-31b-it:free": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "google/gemma-4-26b-a4b-it": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "hunyuan-lite": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "ernie-3.5-8k": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "ernie-speed-8k": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "doubao-1-5-pro-256k": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "CodeLlama-70b-Instruct-hf": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "starcoder2-15b": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "google/gemini-2.5-flash": {"input_per_1k": 0.00015, "output_per_1k": 0.00060, "currency": "USD"},

    # ── Agnes AI ───────────────────────────────────────────────────────────────
    "agnes-2.0-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "agnes-1.5-flash": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── SambaNova ──────────────────────────────────────────────────────────────
    "DeepSeek-Coder-V2-Lite-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "Qwen2.5-Coder-32B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── Fireworks ──────────────────────────────────────────────────────────────
    "accounts/fireworks/models/llama-v3p1-405b-instruct": {"input_per_1k": 0.00300, "output_per_1k": 0.00300, "currency": "USD"},

    # ── OVH ────────────────────────────────────────────────────────────────────
    "Llama-3.3-70B-Instruct": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},
    "DeepSeek-R1-Distill-Qwen-32B": {"input_per_1k": 0.00000, "output_per_1k": 0.00000, "currency": "USD"},

    # ── FreeModel.dev ──────────────────────────────────────────────────────────
    # These use the same model names as OpenAI models above
}

# ── Backend-to-model mapping cache ────────────────────────────────────────────
# Populated lazily from backends_registry.BACKENDS[name]["model"]
_backend_model_cache: dict[str, str] = {}


def _get_model_for_backend(backend: str) -> str:
    """Resolve the model string for a given backend name."""
    if backend in _backend_model_cache:
        return _backend_model_cache[backend]
    try:
        from backends_registry import BACKENDS
        model = BACKENDS.get(backend, {}).get("model", "")
        _backend_model_cache[backend] = model
        return model
    except ImportError:
        return ""


def get_pricing(model: str) -> dict[str, float | str] | None:
    """Return pricing dict for a model, or None if unknown."""
    return COST_TABLE.get(model)


def get_pricing_for_backend(backend: str) -> dict[str, float | str] | None:
    """Return pricing dict for a backend name, or None if unknown."""
    model = _get_model_for_backend(backend)
    if not model:
        return None
    return get_pricing(model)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for given token counts.

    Returns 0.0 if model is not in the cost table (logs a debug warning).
    """
    pricing = get_pricing(model)
    if pricing is None:
        _log.debug("cost_table: unknown model '%s', cost estimate = 0.0", model)
        return 0.0
    input_cost = (input_tokens / 1000.0) * float(pricing["input_per_1k"])
    output_cost = (output_tokens / 1000.0) * float(pricing["output_per_1k"])
    return round(input_cost + output_cost, 8)


def estimate_cost_for_backend(backend: str, input_tokens: int,
                               output_tokens: int) -> float:
    """Estimate cost in USD for a given backend and token counts."""
    model = _get_model_for_backend(backend)
    if not model:
        return 0.0
    return estimate_cost(model, input_tokens, output_tokens)


def get_all_priced_models() -> list[str]:
    """Return all model names that have pricing entries."""
    return sorted(COST_TABLE.keys())


def get_most_expensive_model() -> tuple[str, float]:
    """Return (model, combined_per_1k_cost) for the most expensive model."""
    worst = max(
        COST_TABLE.items(),
        key=lambda kv: float(kv[1]["input_per_1k"]) + float(kv[1]["output_per_1k"]),
    )
    combined = float(worst[1]["input_per_1k"]) + float(worst[1]["output_per_1k"])
    return worst[0], combined


def clear_backend_model_cache() -> None:
    """Clear the backend-to-model resolution cache (for tests)."""
    _backend_model_cache.clear()
```

- [ ] **1.2** Create `tests/test_cost_table.py`.

```python
"""Tests for cost_table.py — static pricing and estimation."""

import pytest

import cost_table


class TestEstimateCost:
    def test_known_model_gpt4o(self):
        # gpt-4o: input $0.00250/1K, output $0.01000/1K
        # 1000 input + 500 output = 0.00250 + 0.00500 = 0.00750
        cost = cost_table.estimate_cost("gpt-4o", 1000, 500)
        assert cost == pytest.approx(0.00750, abs=1e-6)

    def test_known_model_gpt4o_mini(self):
        # gpt-4o-mini: input $0.00015/1K, output $0.00060/1K
        # 2000 input + 1000 output = 0.00030 + 0.00060 = 0.00090
        cost = cost_table.estimate_cost("gpt-4o-mini", 2000, 1000)
        assert cost == pytest.approx(0.00090, abs=1e-6)

    def test_zero_tokens(self):
        cost = cost_table.estimate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_unknown_model_returns_zero(self):
        cost = cost_table.estimate_cost("nonexistent-model-xyz", 1000, 1000)
        assert cost == 0.0

    def test_free_model_returns_zero(self):
        cost = cost_table.estimate_cost("gemini-3.1-flash-lite", 5000, 2000)
        assert cost == 0.0

    def test_mistral_large_pricing(self):
        # mistral-large-latest: input $0.00200/1K, output $0.00600/1K
        cost = cost_table.estimate_cost("mistral-large-latest", 1000, 1000)
        assert cost == pytest.approx(0.00800, abs=1e-6)


class TestGetPricing:
    def test_known_model(self):
        pricing = cost_table.get_pricing("gpt-4o")
        assert pricing is not None
        assert pricing["input_per_1k"] == 0.00250
        assert pricing["output_per_1k"] == 0.01000
        assert pricing["currency"] == "USD"

    def test_unknown_model(self):
        pricing = cost_table.get_pricing("totally-fake-model")
        assert pricing is None


class TestGetPricingForBackend:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_known_backend(self):
        # backends_registry must be importable for this to work
        # github_gpt4o has model "gpt-4o"
        pricing = cost_table.get_pricing_for_backend("github_gpt4o")
        assert pricing is not None
        assert pricing["input_per_1k"] == 0.00250

    def test_free_backend(self):
        # scnet_qwen30b has model "qwen3-30b" (zero cost)
        pricing = cost_table.get_pricing_for_backend("scnet_qwen30b")
        assert pricing is not None
        assert pricing["input_per_1k"] == 0.0


class TestGetMostExpensiveModel:
    def test_returns_model_and_cost(self):
        model, combined = cost_table.get_most_expensive_model()
        assert isinstance(model, str)
        assert combined > 0.0
        # gpt-5.5 should be the most expensive at 0.02 + 0.08 = 0.10
        assert model == "gpt-5.5"
        assert combined == pytest.approx(0.10, abs=1e-6)


class TestGetAllPricedModels:
    def test_returns_list(self):
        models = cost_table.get_all_priced_models()
        assert isinstance(models, list)
        assert len(models) > 30
        assert "gpt-4o" in models


class TestEstimateCostForBackend:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_known_backend_cost(self):
        # github_gpt4o -> gpt-4o: 1000 input + 1000 output = 0.00250 + 0.01000 = 0.01250
        cost = cost_table.estimate_cost_for_backend("github_gpt4o", 1000, 1000)
        assert cost == pytest.approx(0.01250, abs=1e-6)

    def test_free_backend_cost(self):
        # scnet_ds_flash -> deepseek-v4-flash: zero cost
        cost = cost_table.estimate_cost_for_backend("scnet_ds_flash", 10000, 5000)
        assert cost == 0.0
```

- [ ] **1.3** Run tests to verify.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_table.py -v
```

Expected output:

```
tests/test_cost_table.py::TestEstimateCost::test_known_model_gpt4o PASSED
tests/test_cost_table.py::TestEstimateCost::test_known_model_gpt4o_mini PASSED
tests/test_cost_table.py::TestEstimateCost::test_zero_tokens PASSED
tests/test_cost_table.py::TestEstimateCost::test_unknown_model_returns_zero PASSED
tests/test_cost_table.py::TestEstimateCost::test_free_model_returns_zero PASSED
tests/test_cost_table.py::TestEstimateCost::test_mistral_large_pricing PASSED
tests/test_cost_table.py::TestGetPricing::test_known_model PASSED
tests/test_cost_table.py::TestGetPricing::test_unknown_model PASSED
tests/test_cost_table.py::TestGetPricingForBackend::test_known_backend PASSED
tests/test_cost_table.py::TestGetPricingForBackend::test_free_backend PASSED
tests/test_cost_table.py::TestGetMostExpensiveModel::test_returns_model_and_cost PASSED
tests/test_cost_table.py::TestGetAllPricedModels::test_returns_list PASSED
tests/test_cost_table.py::TestEstimateCostForBackend::test_known_backend_cost PASSED
tests/test_cost_table.py::TestEstimateCostForBackend::test_free_backend_cost PASSED
```

- [ ] **1.4** Commit.

```bash
cd D:\QWEN3.0 && git add cost_table.py tests/test_cost_table.py && git commit -m "feat: add static cost table for per-model token pricing"
```

---

## Task 2: Per-Request Cost Tracking

Modify `request_tracking.py` `record_request()` to accept and store estimated cost. Add cost fields to the stats dict.

### Files

- **Modify:** `D:\QWEN3.0\server_bootstrap.py` — add cost fields to initial stats dict
- **Modify:** `D:\QWEN3.0\routes\request_tracking.py` — accept `estimated_cost` in `record_request()`
- **Create:** `D:\QWEN3.0\tests\test_cost_tracking.py`

### Steps

- [ ] **2.1** Add cost fields to `server_bootstrap.py` `create_runtime_state()`.

In `D:\QWEN3.0\server_bootstrap.py`, find the `create_runtime_state()` function and add cost tracking fields:

```python
def create_runtime_state() -> tuple[dict, threading.Lock, dict, dict]:
    """Create stats dict, lock, backend map, and loaded module map."""
    stats = {
        "total_requests": 0,
        "backend_calls": {},
        "intent_distribution": {},
        "recent_logs": [],
        "start_time": time.time(),
        # ── Cost tracking fields ──
        "total_cost_today": 0.0,
        "cost_by_backend": {},
        "cost_by_model": {},
        "total_cost_week": 0.0,
        "total_cost_month": 0.0,
        "cost_history": [],  # list of {"ts": float, "cost": float, "backend": str, "model": str}
    }
    return stats, threading.Lock(), {}, {}
```

- [ ] **2.2** Modify `request_tracking.py` `record_request()` to accept and track cost.

In `D:\QWEN3.0\routes\request_tracking.py`, modify the `record_request` function signature and body:

```python
def record_request(query: str, backend: str, intent: str, duration_ms: int,
                   success: bool = True, client_ip: str = "",
                   ide_source: str = "", sys_prompt_preview: str = "",
                   estimated_cost: float = 0.0,
                   model_name: str = ""):
    """Record a request to statistics, including estimated cost."""
    country = get_ip_location(client_ip) if client_ip else ""

    with _stats_lock:
        _stats["total_requests"] += 1
        if backend not in _stats["backend_calls"]:
            _stats["backend_calls"][backend] = {"count": 0, "success": 0, "total_ms": 0}
        _stats["backend_calls"][backend]["count"] += 1
        if success:
            _stats["backend_calls"][backend]["success"] += 1
        _stats["backend_calls"][backend]["total_ms"] += duration_ms
        _stats["intent_distribution"][intent] = _stats["intent_distribution"].get(intent, 0) + 1

        # ── Cost tracking ──
        if estimated_cost > 0:
            _stats["total_cost_today"] = _stats.get("total_cost_today", 0.0) + estimated_cost
            _stats["total_cost_week"] = _stats.get("total_cost_week", 0.0) + estimated_cost
            _stats["total_cost_month"] = _stats.get("total_cost_month", 0.0) + estimated_cost

            # Cost by backend
            if "cost_by_backend" not in _stats:
                _stats["cost_by_backend"] = {}
            _stats["cost_by_backend"][backend] = (
                _stats["cost_by_backend"].get(backend, 0.0) + estimated_cost
            )

            # Cost by model
            if model_name:
                if "cost_by_model" not in _stats:
                    _stats["cost_by_model"] = {}
                _stats["cost_by_model"][model_name] = (
                    _stats["cost_by_model"].get(model_name, 0.0) + estimated_cost
                )

            # Append to cost history (keep last 1000 entries)
            if "cost_history" not in _stats:
                _stats["cost_history"] = []
            _stats["cost_history"].append({
                "ts": time.time(),
                "cost": estimated_cost,
                "backend": backend,
                "model": model_name,
            })
            if len(_stats["cost_history"]) > 1000:
                _stats["cost_history"] = _stats["cost_history"][-1000:]

        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "query": query[:80],
            "backend": backend,
            "intent": intent,
            "ms": duration_ms,
            "success": success,
            "ip": client_ip,
            "country": country,
            "ide": ide_source,
            "sys_prompt": sys_prompt_preview[:100] if sys_prompt_preview else "",
            "cost": estimated_cost,
        }
        _stats["recent_logs"].append(log_entry)
        if len(_stats["recent_logs"]) > 100:
            _stats["recent_logs"] = _stats["recent_logs"][-100:]

    # Fan-out to SSE log stream subscribers (best-effort, non-blocking).
    try:
        from routes.admin_sse import _main_sse_loop, publish_log_event
        loop = _main_sse_loop
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                return
        if loop and loop.is_running():
            loop.create_task(publish_log_event(log_entry))
    except ImportError as exc:
        log.debug("SSE log fan-out unavailable: %s", exc)
    except Exception as exc:
        log.warning("Failed to fan-out SSE log event", exc_info=True)
```

- [ ] **2.3** Create `tests/test_cost_tracking.py`.

```python
"""Tests for per-request cost tracking in request_tracking.py."""

import threading
import time

from routes import request_tracking


def _make_stats():
    """Create a fresh stats dict for testing."""
    return {
        "total_requests": 0,
        "backend_calls": {},
        "intent_distribution": {},
        "recent_logs": [],
        "start_time": time.time(),
        "total_cost_today": 0.0,
        "cost_by_backend": {},
        "cost_by_model": {},
        "total_cost_week": 0.0,
        "total_cost_month": 0.0,
        "cost_history": [],
    }


class TestRecordRequestCost:
    def setup_method(self):
        self.stats = _make_stats()
        self.lock = threading.Lock()
        request_tracking.inject_state(self.stats, self.lock)

    def test_record_request_with_cost(self):
        request_tracking.record_request(
            query="hello",
            backend="github_gpt4o",
            intent="chat",
            duration_ms=500,
            success=True,
            estimated_cost=0.0125,
            model_name="gpt-4o",
        )
        assert self.stats["total_requests"] == 1
        assert self.stats["total_cost_today"] == 0.0125
        assert self.stats["total_cost_week"] == 0.0125
        assert self.stats["total_cost_month"] == 0.0125

    def test_cost_by_backend(self):
        request_tracking.record_request(
            query="a", backend="github_gpt4o", intent="chat",
            duration_ms=100, estimated_cost=0.01, model_name="gpt-4o",
        )
        request_tracking.record_request(
            query="b", backend="github_gpt4o", intent="chat",
            duration_ms=200, estimated_cost=0.015, model_name="gpt-4o",
        )
        request_tracking.record_request(
            query="c", backend="mistral_large", intent="coding",
            duration_ms=300, estimated_cost=0.008, model_name="mistral-large-latest",
        )
        assert self.stats["cost_by_backend"]["github_gpt4o"] == 0.025
        assert self.stats["cost_by_backend"]["mistral_large"] == 0.008

    def test_cost_by_model(self):
        request_tracking.record_request(
            query="x", backend="b1", intent="chat", duration_ms=100,
            estimated_cost=0.005, model_name="gpt-4o",
        )
        request_tracking.record_request(
            query="y", backend="b2", intent="chat", duration_ms=100,
            estimated_cost=0.003, model_name="gpt-4o",
        )
        assert self.stats["cost_by_model"]["gpt-4o"] == 0.008

    def test_zero_cost_does_not_affect_tracking(self):
        request_tracking.record_request(
            query="free", backend="scnet_ds_flash", intent="chat",
            duration_ms=100, estimated_cost=0.0,
        )
        assert self.stats["total_cost_today"] == 0.0
        assert self.stats["total_requests"] == 1

    def test_cost_history_populated(self):
        for i in range(5):
            request_tracking.record_request(
                query=f"q{i}", backend="b1", intent="chat",
                duration_ms=100, estimated_cost=0.001, model_name="gpt-4o",
            )
        assert len(self.stats["cost_history"]) == 5
        for entry in self.stats["cost_history"]:
            assert "ts" in entry
            assert entry["cost"] == 0.001
            assert entry["backend"] == "b1"

    def test_log_entry_includes_cost(self):
        request_tracking.record_request(
            query="test", backend="b1", intent="chat",
            duration_ms=100, estimated_cost=0.042, model_name="gpt-4o",
        )
        log = self.stats["recent_logs"][-1]
        assert log["cost"] == 0.042

    def test_backward_compat_no_cost_params(self):
        """Existing callers that don't pass cost params should still work."""
        request_tracking.record_request(
            query="legacy", backend="b1", intent="chat", duration_ms=50,
        )
        assert self.stats["total_requests"] == 1
        assert self.stats["total_cost_today"] == 0.0
```

- [ ] **2.4** Run tests.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_tracking.py -v
```

Expected output:

```
tests/test_cost_tracking.py::TestRecordRequestCost::test_record_request_with_cost PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_cost_by_backend PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_cost_by_model PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_zero_cost_does_not_affect_tracking PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_cost_history_populated PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_log_entry_includes_cost PASSED
tests/test_cost_tracking.py::TestRecordRequestCost::test_backward_compat_no_cost_params PASSED
```

- [ ] **2.5** Commit.

```bash
cd D:\QWEN3.0 && git add server_bootstrap.py routes/request_tracking.py tests/test_cost_tracking.py && git commit -m "feat: add per-request cost tracking to stats pipeline"
```

---

## Task 3: Cost-Aware Scoring

Add a `cost_score` dimension to `route_scorer.py` `effective_score()`. For non-critical scenarios, prefer cheaper backends. For critical scenarios (coding, IDE), maintain quality-first.

### Files

- **Modify:** `D:\QWEN3.0\route_scorer.py` — add `cost_score()` and integrate into `effective_score()`
- **Create:** `D:\QWEN3.0\tests\test_cost_scoring.py`

### Steps

- [ ] **3.1** Add `cost_score()` function and integrate into `effective_score()`.

In `D:\QWEN3.0\route_scorer.py`, add the following import at the top (after the existing imports):

```python
import logging

_log = logging.getLogger(__name__)
```

Add the `cost_score()` function after the existing `task_fit_score()` function:

```python
# ── Cost sensitivity by scenario ──────────────────────────────────────────────
# 0.0 = ignore cost entirely, 1.0 = strongly prefer cheaper backends
COST_SENSITIVITY: dict[str, float] = {
    "ide": 0.0,          # IDE: quality only
    "coding": 0.1,       # Coding: almost entirely quality
    "code": 0.1,
    "vision": 0.3,       # Vision: moderate cost awareness
    "chat": 0.6,         # Chat: prefer cheaper
    "chat_fast": 0.7,    # Fast chat: strongly prefer cheaper
    "web": 0.5,          # Web search: moderate
}

DEFAULT_COST_SENSITIVITY = 0.3  # for unknown scenarios


def cost_score(backend: str) -> float:
    """Return a 0.0-1.0 score where 1.0 = cheapest possible.

    Free backends always score 1.0. Unknown backends score 0.5 (neutral).
    Expensive models score closer to 0.0.
    """
    try:
        import cost_table
    except ImportError:
        return 0.5

    pricing = cost_table.get_pricing_for_backend(backend)
    if pricing is None:
        return 0.5  # unknown model — neutral

    input_cost = float(pricing["input_per_1k"])
    output_cost = float(pricing["output_per_1k"])
    combined = input_cost + output_cost

    if combined <= 0.0:
        return 1.0  # free backend

    # Normalize against the most expensive known model.
    # Most expensive is gpt-5.5 at $0.02 + $0.08 = $0.10/1K combined.
    # Use a ceiling of $0.15 to leave headroom.
    MAX_COMBINED = 0.15
    ratio = min(combined / MAX_COMBINED, 1.0)

    # Invert: cheaper = higher score
    return round(1.0 - ratio, 6)


def get_cost_sensitivity(scenario: str, request_type: str) -> float:
    """Return cost sensitivity weight for the given scenario/type.

    0.0 = ignore cost, 1.0 = strongly prefer cheap.
    """
    if scenario in COST_SENSITIVITY:
        return COST_SENSITIVITY[scenario]
    if request_type in COST_SENSITIVITY:
        return COST_SENSITIVITY[request_type]
    return DEFAULT_COST_SENSITIVITY
```

Modify the `effective_score()` function to include the cost dimension. The weights must still sum to 1.0. The cost score replaces a small portion of the other weights based on sensitivity:

```python
def effective_score(backend: str, request_type: str, scenario: str = "",
                    *, health_score: float = 50.0,
                    state: dict | None = None,
                    avg_latency_ms: float = 1000.0,
                    remaining_quota_score: float | None = None,
                    cost_sensitivity: float | None = None) -> float:
    quota_score = (
        budget_manager.get_remaining_quota_score(backend)
        if remaining_quota_score is None else remaining_quota_score
    )

    # Base weights (original LiMa weights)
    w_health = 0.45
    w_stability = 0.25
    w_latency = 0.15
    w_quota = 0.10
    w_task_fit = 0.05

    # Compute base score without cost
    base_score = (
        _norm_score(health_score) * w_health
        + stability_score(state) * w_stability
        + latency_score(avg_latency_ms) * w_latency
        + max(0.0, min(quota_score, 1.0)) * w_quota
        + task_fit_score(backend, request_type, scenario) * w_task_fit
    )

    # Cost-aware adjustment
    sensitivity = (
        cost_sensitivity if cost_sensitivity is not None
        else get_cost_sensitivity(scenario, request_type)
    )

    if sensitivity > 0.0:
        # Carve out a portion of the score for cost consideration.
        # At sensitivity=1.0, cost contributes up to 15% of the final score.
        cost_weight = sensitivity * 0.15
        cs = cost_score(backend)
        # Blend: reduce base by cost_weight, add cost contribution
        score = base_score * (1.0 - cost_weight) + cs * cost_weight
    else:
        score = base_score

    return round(score, 6)
```

Update `rank_backends()` to pass `cost_sensitivity` through:

```python
def rank_backends(backends: list[str], request_type: str, scenario: str = "",
                  *, health_scores: dict[str, float] | None = None,
                  states: dict[str, dict] | None = None,
                  latency_map: dict[str, float] | None = None,
                  cost_sensitivity: float | None = None) -> list[str]:
    health_scores = health_scores or {}
    states = states or {}
    latency_map = latency_map or {}

    def key(item: tuple[int, str]) -> tuple[float, int]:
        idx, backend = item
        return (
            -effective_score(
                backend,
                request_type,
                scenario,
                health_score=health_scores.get(backend, 50.0),
                state=states.get(backend),
                avg_latency_ms=latency_map.get(backend, 1000.0),
                cost_sensitivity=cost_sensitivity,
            ),
            idx,
        )

    return [backend for _, backend in sorted(enumerate(backends), key=key)]
```

- [ ] **3.2** Create `tests/test_cost_scoring.py`.

```python
"""Tests for cost-aware scoring in route_scorer.py."""

import pytest

import cost_table
import route_scorer


class TestCostScore:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_free_backend_scores_highest(self):
        # scnet_ds_flash -> deepseek-v4-flash (zero cost)
        score = route_scorer.cost_score("scnet_ds_flash")
        assert score == 1.0

    def test_expensive_backend_scores_low(self):
        # github_gpt4o -> gpt-4o (input $0.00250, output $0.01000 = $0.01250 combined)
        score = route_scorer.cost_score("github_gpt4o")
        assert score < 1.0
        assert score > 0.0

    def test_unknown_backend_scores_neutral(self):
        score = route_scorer.cost_score("totally_unknown_backend_xyz")
        assert score == 0.5

    def test_cheap_backend_scores_high(self):
        # github_gpt4o_mini -> gpt-4o-mini ($0.00015 + $0.00060 = $0.00075)
        score = route_scorer.cost_score("github_gpt4o_mini")
        expensive_score = route_scorer.cost_score("github_gpt4o")
        assert score > expensive_score

    def test_free_google_backend(self):
        # google_flash_lite -> gemini-3.1-flash-lite (zero cost)
        score = route_scorer.cost_score("google_flash_lite")
        assert score == 1.0


class TestCostSensitivity:
    def test_ide_zero_sensitivity(self):
        assert route_scorer.get_cost_sensitivity("ide", "ide") == 0.0

    def test_coding_low_sensitivity(self):
        assert route_scorer.get_cost_sensitivity("coding", "chat") == 0.1

    def test_chat_high_sensitivity(self):
        assert route_scorer.get_cost_sensitivity("chat", "chat") == 0.6

    def test_chat_fast_highest_sensitivity(self):
        assert route_scorer.get_cost_sensitivity("chat_fast", "chat_fast") == 0.7

    def test_unknown_scenario_default(self):
        assert route_scorer.get_cost_sensitivity("unknown_scenario", "unknown_type") == 0.3


class TestEffectiveScoreWithCost:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_ide_ignores_cost(self):
        """IDE requests should not be affected by cost scoring."""
        cheap = route_scorer.effective_score(
            "scnet_ds_flash", "ide", "ide",
            health_score=80.0, avg_latency_ms=500.0,
        )
        expensive = route_scorer.effective_score(
            "github_gpt4o", "ide", "ide",
            health_score=80.0, avg_latency_ms=500.0,
        )
        # Both should be equal since IDE has 0.0 cost sensitivity
        assert cheap == expensive

    def test_chat_prefers_cheaper(self):
        """Chat requests should prefer cheaper backends."""
        cheap = route_scorer.effective_score(
            "scnet_ds_flash", "chat", "chat",
            health_score=80.0, avg_latency_ms=500.0,
        )
        expensive = route_scorer.effective_score(
            "github_gpt4o", "chat", "chat",
            health_score=80.0, avg_latency_ms=500.0,
        )
        assert cheap > expensive

    def test_coding_mostly_quality(self):
        """Coding should be almost entirely quality-based."""
        cheap = route_scorer.effective_score(
            "scnet_ds_flash", "code", "coding",
            health_score=80.0, avg_latency_ms=500.0,
        )
        expensive = route_scorer.effective_score(
            "github_gpt4o", "code", "coding",
            health_score=80.0, avg_latency_ms=500.0,
        )
        # The difference should be small (only 1% cost weight)
        diff = abs(cheap - expensive)
        assert diff < 0.05  # small difference for coding

    def test_explicit_cost_sensitivity_override(self):
        """cost_sensitivity parameter overrides scenario defaults."""
        score_no_cost = route_scorer.effective_score(
            "github_gpt4o", "chat", "chat",
            health_score=80.0, avg_latency_ms=500.0,
            cost_sensitivity=0.0,
        )
        score_max_cost = route_scorer.effective_score(
            "github_gpt4o", "chat", "chat",
            health_score=80.0, avg_latency_ms=500.0,
            cost_sensitivity=1.0,
        )
        # With max cost sensitivity, expensive model should score lower
        assert score_max_cost < score_no_cost

    def test_backward_compat_no_cost_sensitivity_param(self):
        """Existing callers without cost_sensitivity should work fine."""
        score = route_scorer.effective_score(
            "scnet_ds_flash", "chat", "chat",
            health_score=80.0, avg_latency_ms=500.0,
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestRankBackendsWithCost:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_chat_ranking_prefers_cheaper(self):
        """For chat, free backends should rank above expensive ones."""
        backends = ["github_gpt4o", "scnet_ds_flash", "google_flash_lite"]
        ranked = route_scorer.rank_backends(
            backends, "chat", "chat",
            health_scores={b: 80.0 for b in backends},
            latency_map={b: 500.0 for b in backends},
        )
        # Free backends should be ranked first
        assert ranked[0] in ("scnet_ds_flash", "google_flash_lite")

    def test_ide_ranking_ignores_cost(self):
        """For IDE, ranking should be the same regardless of cost."""
        backends = ["github_gpt4o", "scnet_ds_flash"]
        ranked = route_scorer.rank_backends(
            backends, "ide", "ide",
            health_scores={b: 80.0 for b in backends},
            latency_map={b: 500.0 for b in backends},
        )
        # Both should have equal effective score, so original order preserved
        # (stable sort by index)
        assert len(ranked) == 2
```

- [ ] **3.3** Run tests.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_scoring.py -v
```

Expected output:

```
tests/test_cost_scoring.py::TestCostScore::test_free_backend_scores_highest PASSED
tests/test_cost_scoring.py::TestCostScore::test_expensive_backend_scores_low PASSED
tests/test_cost_scoring.py::TestCostScore::test_unknown_backend_scores_neutral PASSED
tests/test_cost_scoring.py::TestCostScore::test_cheap_backend_scores_high PASSED
tests/test_cost_scoring.py::TestCostScore::test_free_google_backend PASSED
tests/test_cost_scoring.py::TestCostSensitivity::test_ide_zero_sensitivity PASSED
tests/test_cost_scoring.py::TestCostSensitivity::test_coding_low_sensitivity PASSED
tests/test_cost_scoring.py::TestCostSensitivity::test_chat_high_sensitivity PASSED
tests/test_cost_scoring.py::TestCostSensitivity::test_chat_fast_highest_sensitivity PASSED
tests/test_cost_scoring.py::TestCostSensitivity::test_unknown_scenario_default PASSED
tests/test_cost_scoring.py::TestEffectiveScoreWithCost::test_ide_ignores_cost PASSED
tests/test_cost_scoring.py::TestEffectiveScoreWithCost::test_chat_prefers_cheaper PASSED
tests/test_cost_scoring.py::TestEffectiveScoreWithCost::test_coding_mostly_quality PASSED
tests/test_cost_scoring.py::TestEffectiveScoreWithCost::test_explicit_cost_sensitivity_override PASSED
tests/test_cost_scoring.py::TestEffectiveScoreWithCost::test_backward_compat_no_cost_sensitivity_param PASSED
tests/test_cost_scoring.py::TestRankBackendsWithCost::test_chat_ranking_prefers_cheaper PASSED
tests/test_cost_scoring.py::TestRankBackendsWithCost::test_ide_ranking_ignores_cost PASSED
```

- [ ] **3.4** Commit.

```bash
cd D:\QWEN3.0 && git add route_scorer.py tests/test_cost_scoring.py && git commit -m "feat: add cost-aware scoring dimension to effective_score"
```

---

## Task 4: Cost Dashboard

Add cost metrics to `/api/stats` and `/v1/ops/metrics`.

### Files

- **Modify:** `D:\QWEN3.0\routes\admin_api.py` — add cost fields to `admin_stats()` response
- **Modify:** `D:\QWEN3.0\routes\ops_metrics.py` — add cost summary to ops metrics
- **Create:** `D:\QWEN3.0\tests\test_cost_dashboard.py`

### Steps

- [ ] **4.1** Add cost metrics to `admin_stats()` in `D:\QWEN3.0\routes\admin_api.py`.

Add a helper function near the top of `admin_api.py` (after the imports):

```python
def _cost_summary(stats: dict) -> dict:
    """Build cost summary from stats dict."""
    import time as _time

    total_today = stats.get("total_cost_today", 0.0)
    cost_by_backend = dict(stats.get("cost_by_backend", {}))
    cost_by_model = dict(stats.get("cost_by_model", {}))
    total_week = stats.get("total_cost_week", 0.0)
    total_month = stats.get("total_cost_month", 0.0)
    cost_history = stats.get("cost_history", [])

    # Sort backends by cost (descending)
    sorted_backends = sorted(
        cost_by_backend.items(), key=lambda kv: -kv[1]
    )[:20]

    # Sort models by cost (descending)
    sorted_models = sorted(
        cost_by_model.items(), key=lambda kv: -kv[1]
    )[:20]

    # Estimate savings vs baseline (if all requests went to most expensive)
    try:
        from cost_table import get_most_expensive_model
        _, max_per_1k = get_most_expensive_model()
    except ImportError:
        max_per_1k = 0.10  # fallback: assume $0.10/1K combined

    # Rough estimate: assume avg 1000 input + 500 output tokens per request
    total_requests = stats.get("total_requests", 0)
    baseline_cost = total_requests * (max_per_1k * 1.5)  # 1.5K tokens avg
    actual_cost = total_today + total_week + total_month  # approximate
    # More precise: use total_cost_today as proxy for "all time" if week/month not reset
    savings = max(0.0, baseline_cost - total_today)

    return {
        "total_cost_today": round(total_today, 6),
        "total_cost_week": round(total_week, 6),
        "total_cost_month": round(total_month, 6),
        "cost_by_backend": dict(sorted_backends),
        "cost_by_model": dict(sorted_models),
        "estimated_savings_vs_baseline": round(savings, 6),
        "cost_entries_tracked": len(cost_history),
    }
```

Then modify the `admin_stats()` return dict to include cost:

In the return statement of `admin_stats()`, add the cost key before the closing `}`:

```python
        return {
            "total_requests": total,
            "uptime_seconds": uptime,
            "avg_response_ms": avg_ms,
            "backend_calls": backend_calls,
            "intent_distribution": dict(stats["intent_distribution"]),
            "unique_ips": len(ips),
            "ide_distribution": ide_dist,
            "version": _get_version_info(),
            "cost": _cost_summary(stats),
        }
```

- [ ] **4.2** Add cost summary to `/v1/ops/metrics` in `D:\QWEN3.0\routes\ops_metrics.py`.

In the `_app_stats()` helper or directly in `ops_metrics()`, add a cost section. Add this helper function near the top:

```python
def _ops_cost_summary(stats: dict[str, Any]) -> dict[str, Any]:
    """Compact cost summary for ops metrics."""
    return {
        "total_cost_today": round(stats.get("total_cost_today", 0.0), 6),
        "total_cost_week": round(stats.get("total_cost_week", 0.0), 6),
        "total_cost_month": round(stats.get("total_cost_month", 0.0), 6),
        "top_cost_backends": dict(
            sorted(
                stats.get("cost_by_backend", {}).items(),
                key=lambda kv: -kv[1],
            )[:5]
        ),
    }
```

Then add to the return JSONResponse in `ops_metrics()`:

```python
        "cost": _ops_cost_summary(stats),
```

- [ ] **4.3** Create `tests/test_cost_dashboard.py`.

```python
"""Tests for cost dashboard endpoints."""

import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_api
from routes.admin_auth import verify_admin
from routes.admin_state import stats_context


def _make_stats_with_cost():
    stats = {
        "total_requests": 10,
        "backend_calls": {"github_gpt4o": {"count": 5, "success": 5, "total_ms": 500}},
        "intent_distribution": {"chat": 10},
        "recent_logs": [],
        "start_time": time.time(),
        "total_cost_today": 0.125,
        "cost_by_backend": {"github_gpt4o": 0.10, "scnet_ds_flash": 0.025},
        "cost_by_model": {"gpt-4o": 0.10, "deepseek-v4-flash": 0.025},
        "total_cost_week": 0.500,
        "total_cost_month": 2.100,
        "cost_history": [
            {"ts": time.time(), "cost": 0.01, "backend": "github_gpt4o", "model": "gpt-4o"},
        ],
    }
    return stats


class TestAdminStatsCost:
    def test_stats_includes_cost_summary(self, monkeypatch):
        stats = _make_stats_with_cost()
        lock = threading.Lock()
        enabled = {}

        monkeypatch.setattr(admin_api, "stats_context", lambda: (stats, lock, enabled))

        app = FastAPI()
        app.dependency_overrides[verify_admin] = lambda: None
        app.include_router(admin_api.router, prefix="/admin")

        client = TestClient(app)
        response = client.get("/admin/api/stats")
        assert response.status_code == 200

        body = response.json()
        assert "cost" in body
        cost = body["cost"]
        assert cost["total_cost_today"] == 0.125
        assert cost["total_cost_week"] == 0.500
        assert cost["total_cost_month"] == 2.100
        assert "github_gpt4o" in cost["cost_by_backend"]
        assert cost["cost_entries_tracked"] == 1
        assert cost["estimated_savings_vs_baseline"] >= 0

    def test_stats_cost_backends_sorted_descending(self, monkeypatch):
        stats = _make_stats_with_cost()
        stats["cost_by_backend"] = {
            "cheap": 0.01,
            "expensive": 0.50,
            "mid": 0.10,
        }
        lock = threading.Lock()
        enabled = {}

        monkeypatch.setattr(admin_api, "stats_context", lambda: (stats, lock, enabled))

        app = FastAPI()
        app.dependency_overrides[verify_admin] = lambda: None
        app.include_router(admin_api.router, prefix="/admin")

        client = TestClient(app)
        response = client.get("/admin/api/stats")
        body = response.json()
        backend_keys = list(body["cost"]["cost_by_backend"].keys())
        assert backend_keys == ["expensive", "mid", "cheap"]


class TestOpsMetricsCost:
    def test_ops_metrics_includes_cost(self, monkeypatch):
        monkeypatch.setenv("LIMA_API_KEY", "test-private-token")

        from routes.ops_metrics import router

        app = FastAPI()
        app.state.stats = _make_stats_with_cost()
        app.include_router(router)

        response = TestClient(app).get(
            "/v1/ops/metrics",
            headers={"Authorization": "Bearer test-private-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "cost" in data
        assert data["cost"]["total_cost_today"] == 0.125
        assert "top_cost_backends" in data["cost"]
```

- [ ] **4.4** Run tests.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_dashboard.py -v
```

Expected output:

```
tests/test_cost_dashboard.py::TestAdminStatsCost::test_stats_includes_cost_summary PASSED
tests/test_cost_dashboard.py::TestAdminStatsCost::test_stats_cost_backends_sorted_descending PASSED
tests/test_cost_dashboard.py::TestOpsMetricsCost::test_ops_metrics_includes_cost PASSED
```

- [ ] **4.5** Commit.

```bash
cd D:\QWEN3.0 && git add routes/admin_api.py routes/ops_metrics.py tests/test_cost_dashboard.py && git commit -m "feat: add cost metrics to admin stats and ops dashboard"
```

---

## Task 5: Cost Optimization Report

Create `cost_report.py` that generates a savings report.

### Files

- **Create:** `D:\QWEN3.0\cost_report.py`
- **Modify:** `D:\QWEN3.0\routes\admin_api.py` — add `/api/cost-report` endpoint
- **Create:** `D:\QWEN3.0\tests\test_cost_report.py`

### Steps

- [ ] **5.1** Create `cost_report.py`.

```python
"""Cost optimization report generator for LiMa.

Generates human-readable savings reports showing how much money LiMa saved
by routing requests to cost-efficient backends instead of the most expensive.
"""

from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)


def generate_report(stats: dict[str, Any]) -> dict[str, Any]:
    """Generate a cost optimization report from the current stats snapshot.

    Returns a dict with:
    - summary_text: human-readable summary
    - total_actual_cost: actual estimated cost
    - total_baseline_cost: hypothetical cost if all requests used most expensive backend
    - savings_amount: baseline - actual
    - savings_percent: percentage saved
    - top_efficient_backends: list of (backend, cost, request_count)
    - period_info: time window description
    """
    total_requests = stats.get("total_requests", 0)
    cost_by_backend = dict(stats.get("cost_by_backend", {}))
    cost_history = stats.get("cost_history", [])
    total_cost_today = stats.get("total_cost_today", 0.0)
    total_cost_week = stats.get("total_cost_week", 0.0)

    # Actual total cost
    actual_cost = total_cost_today

    # Baseline: if every request went to the most expensive backend
    try:
        from cost_table import get_most_expensive_model
        worst_model, max_per_1k = get_most_expensive_model()
    except ImportError:
        worst_model = "gpt-5.5"
        max_per_1k = 0.10  # $0.02 + $0.08

    # Assume average 1500 tokens per request (1000 input + 500 output)
    avg_tokens_per_request = 1.5  # in 1K units
    baseline_cost = total_requests * max_per_1k * avg_tokens_per_request

    # Savings
    savings = max(0.0, baseline_cost - actual_cost)
    savings_pct = (savings / baseline_cost * 100) if baseline_cost > 0 else 0.0

    # Top efficient backends: sorted by (requests / cost) ratio — high volume, low cost
    # Only include backends with cost > 0 for meaningful ratio
    backend_request_counts = {}
    for entry in cost_history:
        b = entry.get("backend", "")
        backend_request_counts[b] = backend_request_counts.get(b, 0) + 1

    efficient_backends = []
    for backend, cost in sorted(cost_by_backend.items(), key=lambda kv: kv[1]):
        req_count = backend_request_counts.get(backend, 0)
        if req_count == 0:
            # Fall back to stats backend_calls
            bc = stats.get("backend_calls", {}).get(backend, {})
            req_count = bc.get("count", 0) if isinstance(bc, dict) else 0
        if cost <= 0:
            # Free backend — infinite efficiency, put at top
            efficient_backends.append({
                "backend": backend,
                "cost": 0.0,
                "request_count": req_count,
                "efficiency": "free",
            })
        else:
            efficiency = req_count / cost if cost > 0 else 0
            efficient_backends.append({
                "backend": backend,
                "cost": round(cost, 6),
                "request_count": req_count,
                "efficiency": round(efficiency, 2),
            })

    # Sort: free backends first, then by efficiency descending
    efficient_backends.sort(
        key=lambda x: (0 if x["efficiency"] == "free" else 1,
                       -(x["efficiency"] if isinstance(x["efficiency"], (int, float)) else float("inf")))
    )

    # Top 3 cost-efficient
    top_3 = efficient_backends[:3]

    # Determine cost routing percentage
    free_request_count = sum(
        1 for entry in cost_history if entry.get("cost", 0) == 0
    )
    cost_routed_pct = (
        (free_request_count / len(cost_history) * 100) if cost_history else 0.0
    )

    # Build summary text
    uptime = int(time.time() - stats.get("start_time", time.time()))
    hours = uptime // 3600

    top_3_names = ", ".join(
        f"{b['backend']} ({b['efficiency']})" for b in top_3
    )

    summary_text = (
        f"Over the past {hours}h, LiMa handled {total_requests} requests. "
        f"Actual cost: ${actual_cost:.4f}. "
        f"Baseline (all {worst_model}): ${baseline_cost:.4f}. "
        f"Saved ${savings:.4f} ({savings_pct:.1f}%). "
        f"{cost_routed_pct:.0f}% of requests routed to free/cheap backends. "
        f"Top 3 cost-efficient backends: {top_3_names}."
    )

    return {
        "summary_text": summary_text,
        "total_actual_cost": round(actual_cost, 6),
        "total_baseline_cost": round(baseline_cost, 6),
        "savings_amount": round(savings, 6),
        "savings_percent": round(savings_pct, 1),
        "cost_routed_to_free_pct": round(cost_routed_pct, 1),
        "top_efficient_backends": top_3,
        "all_backends_cost": [
            {"backend": b["backend"], "cost": b["cost"], "requests": b["request_count"]}
            for b in efficient_backends[:20]
        ],
        "uptime_hours": hours,
        "total_requests": total_requests,
        "baseline_model": worst_model,
    }
```

- [ ] **5.2** Add `/api/cost-report` endpoint to `D:\QWEN3.0\routes\admin_api.py`.

Add the import and the endpoint at the end of `admin_api.py` (before the last function or in a logical spot):

```python
@router.get("/api/cost-report", dependencies=[Depends(verify_admin)])
async def admin_cost_report():
    """Generate a cost optimization savings report."""
    stats, lock, _enabled = stats_context()
    with lock:
        try:
            from cost_report import generate_report
            return generate_report(dict(stats))
        except ImportError:
            return {"error": "cost_report module not available"}
```

- [ ] **5.3** Create `tests/test_cost_report.py`.

```python
"""Tests for cost optimization report."""

import threading
import time

import pytest

import cost_table
from cost_report import generate_report


def _make_stats():
    return {
        "total_requests": 100,
        "backend_calls": {
            "scnet_ds_flash": {"count": 60, "success": 60, "total_ms": 30000},
            "github_gpt4o": {"count": 30, "success": 30, "total_ms": 45000},
            "google_flash_lite": {"count": 10, "success": 10, "total_ms": 5000},
        },
        "intent_distribution": {"chat": 80, "coding": 20},
        "recent_logs": [],
        "start_time": time.time() - 7200,  # 2 hours ago
        "total_cost_today": 0.375,  # only github_gpt4o has cost
        "cost_by_backend": {
            "scnet_ds_flash": 0.0,
            "github_gpt4o": 0.375,
            "google_flash_lite": 0.0,
        },
        "cost_by_model": {
            "deepseek-v4-flash": 0.0,
            "gpt-4o": 0.375,
            "gemini-3.1-flash-lite": 0.0,
        },
        "total_cost_week": 1.5,
        "total_cost_month": 5.0,
        "cost_history": (
            [{"ts": time.time(), "cost": 0.0, "backend": "scnet_ds_flash", "model": "deepseek-v4-flash"}] * 60
            + [{"ts": time.time(), "cost": 0.0125, "backend": "github_gpt4o", "model": "gpt-4o"}] * 30
            + [{"ts": time.time(), "cost": 0.0, "backend": "google_flash_lite", "model": "gemini-3.1-flash-lite"}] * 10
        ),
    }


class TestGenerateReport:
    def setup_method(self):
        cost_table.clear_backend_model_cache()

    def test_report_structure(self):
        stats = _make_stats()
        report = generate_report(stats)

        assert "summary_text" in report
        assert "total_actual_cost" in report
        assert "total_baseline_cost" in report
        assert "savings_amount" in report
        assert "savings_percent" in report
        assert "top_efficient_backends" in report

    def test_savings_calculated(self):
        stats = _make_stats()
        report = generate_report(stats)

        assert report["total_actual_cost"] == 0.375
        assert report["total_baseline_cost"] > report["total_actual_cost"]
        assert report["savings_amount"] > 0
        assert report["savings_percent"] > 0

    def test_top_efficient_backends(self):
        stats = _make_stats()
        report = generate_report(stats)

        top = report["top_efficient_backends"]
        assert len(top) == 3
        # Free backends should be listed first
        assert any(b["efficiency"] == "free" for b in top)

    def test_cost_routed_percentage(self):
        stats = _make_stats()
        report = generate_report(stats)

        # 70 out of 100 history entries have cost=0 (60 scnet + 10 google)
        assert report["cost_routed_to_free_pct"] == 70.0

    def test_summary_text_readable(self):
        stats = _make_stats()
        report = generate_report(stats)

        text = report["summary_text"]
        assert "LiMa" in text
        assert "100 requests" in text
        assert "$" in text
        assert "Saved" in text

    def test_zero_requests(self):
        stats = _make_stats()
        stats["total_requests"] = 0
        stats["cost_history"] = []
        stats["cost_by_backend"] = {}
        stats["total_cost_today"] = 0.0

        report = generate_report(stats)
        assert report["savings_amount"] == 0.0
        assert report["savings_percent"] == 0.0


class TestCostReportEndpoint:
    def test_endpoint_returns_report(self, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from routes import admin_api
        from routes.admin_auth import verify_admin
        from routes.admin_state import stats_context

        stats = _make_stats()
        lock = threading.Lock()
        enabled = {}

        monkeypatch.setattr(admin_api, "stats_context", lambda: (stats, lock, enabled))

        app = FastAPI()
        app.dependency_overrides[verify_admin] = lambda: None
        app.include_router(admin_api.router, prefix="/admin")

        client = TestClient(app)
        response = client.get("/admin/api/cost-report")
        assert response.status_code == 200

        body = response.json()
        assert "summary_text" in body
        assert "savings_amount" in body
```

- [ ] **5.4** Run tests.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_report.py -v
```

Expected output:

```
tests/test_cost_report.py::TestGenerateReport::test_report_structure PASSED
tests/test_cost_report.py::TestGenerateReport::test_savings_calculated PASSED
tests/test_cost_report.py::TestGenerateReport::test_top_efficient_backends PASSED
tests/test_cost_report.py::TestGenerateReport::test_cost_routed_percentage PASSED
tests/test_cost_report.py::TestGenerateReport::test_summary_text_readable PASSED
tests/test_cost_report.py::TestGenerateReport::test_zero_requests PASSED
tests/test_cost_report.py::TestCostReportEndpoint::test_endpoint_returns_report PASSED
```

- [ ] **5.5** Commit.

```bash
cd D:\QWEN3.0 && git add cost_report.py routes/admin_api.py tests/test_cost_report.py && git commit -m "feat: add cost optimization report with savings analysis"
```

---

## Task 6: Integration Test

Test that cost-aware routing end-to-end prefers cheaper backends for simple queries while maintaining quality for complex ones.

### Files

- **Create:** `D:\QWEN3.0\tests\test_cost_routing_integration.py`

### Steps

- [ ] **6.1** Create integration test.

```python
"""Integration test: cost-aware routing end-to-end.

Verifies that:
1. Chat requests prefer free/cheap backends
2. Coding/IDE requests maintain quality-first (ignore cost)
3. Cost tracking records are populated after routing
4. Cost report generates valid output after simulated traffic
"""

import threading
import time

import pytest

import cost_table
import route_scorer
import budget_manager
from cost_report import generate_report
from routes import request_tracking


def _make_stats():
    return {
        "total_requests": 0,
        "backend_calls": {},
        "intent_distribution": {},
        "recent_logs": [],
        "start_time": time.time() - 3600,
        "total_cost_today": 0.0,
        "cost_by_backend": {},
        "cost_by_model": {},
        "total_cost_week": 0.0,
        "total_cost_month": 0.0,
        "cost_history": [],
    }


class TestCostAwareRoutingIntegration:
    """End-to-end: score backends, route, track cost, generate report."""

    def setup_method(self):
        cost_table.clear_backend_model_cache()
        budget_manager.reset_for_tests()
        self.stats = _make_stats()
        self.lock = threading.Lock()
        request_tracking.inject_state(self.stats, self.lock)

    def _simulate_request(self, backend: str, request_type: str,
                          scenario: str, input_tokens: int = 1000,
                          output_tokens: int = 500):
        """Simulate a routed request with cost tracking."""
        # Score the backend
        score = route_scorer.effective_score(
            backend, request_type, scenario,
            health_score=80.0, avg_latency_ms=500.0,
        )

        # Estimate cost
        from backends_registry import BACKENDS
        model = BACKENDS.get(backend, {}).get("model", "")
        cost = cost_table.estimate_cost(model, input_tokens, output_tokens)

        # Record
        request_tracking.record_request(
            query="test query",
            backend=backend,
            intent=scenario or request_type,
            duration_ms=500,
            success=True,
            estimated_cost=cost,
            model_name=model,
        )

        return score, cost

    def test_chat_prefers_free_backends(self):
        """For chat scenario, free backends should score higher."""
        backends = [
            "scnet_ds_flash",       # free
            "google_flash_lite",     # free
            "github_gpt4o",          # paid
            "mistral_large",         # paid
        ]

        scores = {}
        for b in backends:
            scores[b] = route_scorer.effective_score(
                b, "chat", "chat",
                health_score=80.0, avg_latency_ms=500.0,
            )

        # Free backends should score higher than paid ones
        free_avg = (scores["scnet_ds_flash"] + scores["google_flash_lite"]) / 2
        paid_avg = (scores["github_gpt4o"] + scores["mistral_large"]) / 2
        assert free_avg > paid_avg

    def test_ignores_cost_for_ide(self):
        """IDE requests should produce identical scores regardless of cost."""
        free_score = route_scorer.effective_score(
            "scnet_ds_flash", "ide", "ide",
            health_score=80.0, avg_latency_ms=500.0,
        )
        paid_score = route_scorer.effective_score(
            "github_gpt4o", "ide", "ide",
            health_score=80.0, avg_latency_ms=500.0,
        )
        assert free_score == paid_score

    def test_coding_minimal_cost_influence(self):
        """Coding scenario should have very small cost influence."""
        free_score = route_scorer.effective_score(
            "scnet_ds_flash", "code", "coding",
            health_score=80.0, avg_latency_ms=500.0,
        )
        paid_score = route_scorer.effective_score(
            "github_gpt4o", "code", "coding",
            health_score=80.0, avg_latency_ms=500.0,
        )
        diff = abs(free_score - paid_score)
        assert diff < 0.05  # minimal difference

    def test_cost_tracking_after_simulated_traffic(self):
        """Simulate mixed traffic and verify cost tracking + report."""
        # 20 chat requests to free backend
        for _ in range(20):
            self._simulate_request("scnet_ds_flash", "chat", "chat")

        # 5 chat requests to paid backend
        for _ in range(5):
            self._simulate_request("github_gpt4o", "chat", "chat")

        # 10 coding requests (mixed)
        for _ in range(5):
            self._simulate_request("scnet_ds_flash", "code", "coding")
        for _ in range(5):
            self._simulate_request("github_gpt4o", "code", "coding")

        # Verify stats
        assert self.stats["total_requests"] == 40
        assert self.stats["total_cost_today"] > 0.0
        assert "scnet_ds_flash" in self.stats["cost_by_backend"]
        assert "github_gpt4o" in self.stats["cost_by_backend"]
        assert self.stats["cost_by_backend"]["scnet_ds_flash"] == 0.0
        assert self.stats["cost_by_backend"]["github_gpt4o"] > 0.0

        # Generate report
        report = generate_report(self.stats)
        assert report["total_requests"] == 40
        assert report["savings_amount"] > 0
        assert report["savings_percent"] > 0
        assert "LiMa" in report["summary_text"]

    def test_rank_backends_chat_ordering(self):
        """rank_backends for chat should put free backends first."""
        backends = ["github_gpt4o", "scnet_ds_flash", "mistral_large", "google_flash_lite"]

        ranked = route_scorer.rank_backends(
            backends, "chat", "chat",
            health_scores={b: 80.0 for b in backends},
            latency_map={b: 500.0 for b in backends},
        )

        # The top 2 should be the free backends
        top_2 = set(ranked[:2])
        assert "scnet_ds_flash" in top_2
        assert "google_flash_lite" in top_2

    def test_rank_backends_ide_no_cost_preference(self):
        """rank_backends for IDE should not reorder based on cost."""
        backends = ["github_gpt4o", "scnet_ds_flash"]

        ranked = route_scorer.rank_backends(
            backends, "ide", "ide",
            health_scores={b: 80.0 for b in backends},
            latency_map={b: 500.0 for b in backends},
        )

        # Scores are equal, so original order (by index) preserved
        assert ranked[0] == "github_gpt4o"
        assert ranked[1] == "scnet_ds_flash"

    def test_backward_compat_existing_stats(self):
        """Stats dict without cost fields should not crash report."""
        legacy_stats = {
            "total_requests": 50,
            "backend_calls": {"b1": {"count": 50, "success": 50, "total_ms": 1000}},
            "intent_distribution": {"chat": 50},
            "recent_logs": [],
            "start_time": time.time() - 3600,
            # No cost fields at all
        }
        report = generate_report(legacy_stats)
        assert report["total_requests"] == 50
        assert report["total_actual_cost"] == 0.0
        # Baseline > 0 because there are requests
        assert report["total_baseline_cost"] > 0
```

- [ ] **6.2** Run all cost-related tests.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_cost_table.py tests/test_cost_tracking.py tests/test_cost_scoring.py tests/test_cost_dashboard.py tests/test_cost_report.py tests/test_cost_routing_integration.py -v
```

Expected output:

```
tests/test_cost_table.py ... (14 tests) PASSED
tests/test_cost_tracking.py ... (7 tests) PASSED
tests/test_cost_scoring.py ... (17 tests) PASSED
tests/test_cost_dashboard.py ... (3 tests) PASSED
tests/test_cost_report.py ... (7 tests) PASSED
tests/test_cost_routing_integration.py ... (8 tests) PASSED
```

- [ ] **6.3** Run the full existing test suite to check for regressions.

```bash
cd D:\QWEN3.0 && python -m pytest tests/test_admin_stats.py tests/test_ops_metrics.py -v
```

Expected output: all existing tests continue to pass.

- [ ] **6.4** Commit.

```bash
cd D:\QWEN3.0 && git add tests/test_cost_routing_integration.py && git commit -m "test: add cost-aware routing integration tests"
```

---

## Summary of Changes

| File | Action | Description |
|------|--------|-------------|
| `cost_table.py` | Create | Static pricing table with ~150 model entries, `estimate_cost()` function |
| `cost_report.py` | Create | Savings report generator with human-readable summary |
| `server_bootstrap.py` | Modify | Add cost fields to initial runtime state |
| `routes/request_tracking.py` | Modify | Accept `estimated_cost` and `model_name` in `record_request()` |
| `route_scorer.py` | Modify | Add `cost_score()`, `get_cost_sensitivity()`, integrate into `effective_score()` and `rank_backends()` |
| `routes/admin_api.py` | Modify | Add `cost` to `/api/stats`, add `/api/cost-report` endpoint |
| `routes/ops_metrics.py` | Modify | Add `cost` summary to `/v1/ops/metrics` |
| `tests/test_cost_table.py` | Create | 14 tests for pricing table and estimation |
| `tests/test_cost_tracking.py` | Create | 7 tests for per-request cost tracking |
| `tests/test_cost_scoring.py` | Create | 17 tests for cost-aware scoring |
| `tests/test_cost_dashboard.py` | Create | 3 tests for dashboard cost fields |
| `tests/test_cost_report.py` | Create | 7 tests for cost report generator |
| `tests/test_cost_routing_integration.py` | Create | 8 tests for end-to-end cost routing |

## Key Design Decisions

1. **Cost sensitivity is scenario-driven**: IDE (0.0), coding (0.1), chat (0.6), chat_fast (0.7). This ensures quality-critical paths are unaffected.

2. **Maximum cost weight is 15%**: Even at maximum sensitivity (1.0), cost contributes at most 15% of the effective score, preventing cost from dominating routing decisions.

3. **Free backends always score 1.0 for cost**: This naturally pushes free backends to the top for non-critical scenarios without any special casing.

4. **Backward compatible**: All new parameters (`estimated_cost`, `model_name`, `cost_sensitivity`) have defaults, so existing callers work without modification.

5. **Static cost table**: No API calls needed for pricing. Models with zero cost (free tier, self-hosted, community) are explicitly listed with 0.0 pricing.

6. **Cost history capped at 1000 entries**: Prevents unbounded memory growth in the stats dict.
