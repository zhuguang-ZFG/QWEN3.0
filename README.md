# red V1flash — 通用智能路由编排器

> 深圳市动力巢科技有限公司 (www.donglicao.com)

**核心理念：1+N >> N**
一个智能路由器 + N 个后端模型，远大于 N 个模型单独使用。

---

## 架构

```
用户 → Claude Code / Cursor → cc-switch → ngrok → server.py
                                                      │
                                                      ▼
                                              smart_router.py
                                                      │
                              ┌────────────────────────┼────────────────────────┐
                              ▼                        ▼                        ▼
                     三层路由决策                                         
          ┌──────────────────────────────────────────────────────────┐
          │  L0: 预设直答 (0ms)     — 身份/问候/元问题              │
          │  L1: 规则路由 (0ms)     — 关键词匹配，80%命中          │
          │  L2: 本地模型路由 (50-100ms) — Qwen3-1.7B 意图分析     │
          └──────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────────────────┐
              ▼               ▼                           ▼
         免费层 L1       免费层 L2                   付费层 L3
      (LongCat/移动)   (Nvidia/OpenRouter)        (DeepSeek/Claude)
```

---

## 路由策略：免费优先 + 付费兜底

| 层级 | 策略 | 延迟 | 成本 |
|------|------|------|------|
| L0 预设直答 | 身份/问候/能力问题直接返回 | 0ms | 零 |
| L1 规则路由 | 关键词匹配，覆盖80%请求 | 0ms | 零 |
| L2 模型路由 | 本地 Qwen3-1.7B 意图分析 | 50-100ms | 零 |
| 后端 L1 | LongCat/中国移动（免费无限） | 1-3s | 零 |
| 后端 L2 | Nvidia NIM / OpenRouter（免费额度） | 2-5s | 零 |
| 后端 L3 | DeepSeek / Claude（付费兜底） | 2-5s | 按量 |

---

## 支持的后端（26个）

### 免费层 L1 — LongCat / 中国移动（无限额度）

| ID | 模型 | 用途 |
|----|------|------|
| longcat_lite | LongCat-Flash-Lite | 快速通用 |
| longcat_chat | LongCat-Flash-Chat | 通用对话 |
| longcat | LongCat-2.0-Preview | 综合最强 |
| longcat_thinking | LongCat-Flash-Thinking | 推理型 |
| longcat_omni | LongCat-Flash-Omni | 多模态 |
| chinamobile | MiniMax-M25 | 中国移动 MaaS |

### 免费层 L2 — Nvidia NIM

| ID | 模型 | 用途 |
|----|------|------|
| nvidia_qwen_coder | Qwen3-Coder-480B | 代码生成 |
| nvidia_nemotron | Nemotron-Super-49B | 推理 |
| nvidia_phi4 | Phi-4 Mini | 快速轻量 |
| nvidia_llama4 | Llama4 Maverick | 通用 |
| nvidia_llama70b | Llama-3.3-70B | 通用 |
| nvidia_mistral | Mistral Large 675B | 综合 |

### 免费层 L2 — OpenRouter 免费模型

| ID | 模型 | 用途 |
|----|------|------|
| or_deepseek_r1 | DeepSeek V4 Flash | 推理 |
| or_qwen3_235b | Qwen3 Coder | 代码 |
| or_llama70b | Llama-3.3-70B | 通用 |
| or_nemotron | Nemotron-3-Super-120B | 推理 |
| or_qwen3_30b | Qwen3-Next-80B | 通用 |

### 付费层 L3 — 兜底

| ID | 模型 | 用途 |
|----|------|------|
| deepseek_pro | DeepSeek V4 Pro | 综合 |
| deepseek_pro_1m | DeepSeek V4 Pro (1M) | 长上下文 |
| deepseek_flash | DeepSeek V4 Flash | 快速 |
| deepseek_flash_1m | DeepSeek V4 Flash (1M) | 长上下文快速 |
| claude | Claude Sonnet 4.6 | 最强兜底 |
| local | Qwen3-1.7B（训练中） | 本地推理 |

---

<!-- APPEND_MARKER -->

## 当前状态

- Claude Code 已接入（通过 ngrok 隧道 + OpenAI 兼容 API）
- Cursor 已接入（同一接口）
- Round 8 训练数据准备完成
- 三层路由已上线：预设直答 → 规则路由 → 本地模型路由
- 熔断器保护：后端故障自动切换备选

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 路由核心 | Python + FastAPI |
| 本地模型 | Qwen3-1.7B (QLoRA 微调) |
| 协议兼容 | OpenAI ChatCompletion API |
| 隧道 | ngrok |
| 训练 | QLoRA + GRPO |
| 部署 | LM Studio / vLLM |

---

## 快速开始

```bash
# 1. 安装依赖
pip install fastapi uvicorn python-dotenv

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 3. 启动服务
python server.py

# 4. 启动 ngrok 隧道（可选，外网访问）
start_tunnel.bat
```

---

## 核心文件

| 文件 | 用途 |
|------|------|
| `server.py` | OpenAI 兼容 API 层（FastAPI） |
| `smart_router.py` | 智能路由核心（三层路由 + 熔断器） |
| `orchestrate.py` | 多步编排（复杂任务拆解） |
| `model_registry.py` | 后端模型注册与管理 |
| `quota_tracker.py` | 配额追踪 |
| `generate_routing_data.py` | 路由训练数据生成 |
| `train_model.py` | QLoRA 训练脚本 |
| `auto_trainer.py` | 自动训练调度 |
| `eval_loop.py` | 评估循环 |
| `quality_gate.py` | 质量门控 |

---

> 深圳市动力巢科技有限公司 (www.donglicao.com)
