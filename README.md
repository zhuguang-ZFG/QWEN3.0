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

## Superpowers 原则

路由器不只是"选后端"，它是整个系统的大脑。遵循以下原则：

| 原则 | 含义 |
|------|------|
| **永不静默失败** | 任何路径都有 fallback，用户永远能得到回答 |
| **自愈能力** | 后端挂了自动切换，不需要人工干预 |
| **诚实边界** | 搞不定就说搞不定，不瞎编 |
| **越用越强** | 收集真实请求日志，持续训练迭代 |
| **IDE 感知** | 识别用户用的什么工具，调整路由策略 |

---

## Fallback 架构（搞不定怎么办）

```
请求进入
  │
  ▼
[正则快速通道] ─── 命中 ──→ 0ms 直接返回
  │ 未命中
  ▼
[路由模型 Qwen3-1.7B] ─── 输出有效 JSON ──→ 执行路由决策
  │ 无效/超时(>100ms)
  ▼
[默认规则] ─── 按 IDE 类型 + 问题长度选后端
  │
  ▼
[执行路由] ─── 后端正常 ──→ 返回结果
  │ 后端失败
  ▼
[同层降级] ─── 同层级换另一个后端重试
  │ 同层全挂
  ▼
[跨层升级] ─── L1→L2→L3 逐级升级
  │ 全部失败
  ▼
[诚实告知] ─── "当前服务繁忙，请稍后重试" + 记录日志
```

### 质量自检机制

| 场景 | 检测方式 | 处理 |
|------|---------|------|
| 回答太短（<50字） | 长度检测 | 自动升级到更强后端重试 |
| 模型不确定 | complexity>0.7 但路由到 lite | 自动升级 |
| 用户不满意 | UI 反馈按钮 | 重新路由到付费后端 |
| 能力超限 | 模型输出 action:"reject" | 诚实告知 + 记录 |

### 日志驱动迭代

所有"低置信度"和"fallback 触发"的请求自动记录到日志，定期：
1. 人工标注正确路由
2. 加入训练数据
3. 重新训练模型
4. 部署验证

---

## IDE 感知路由（20 层识别特征）

模型通过系统提示词自动识别用户使用的 AI IDE：

| 层级 | 信号 | 置信度 |
|------|------|--------|
| L1 身份行 | "You are Claude Code..." / "Cursor IDE..." | 100% |
| L2 工具名 | Edit/Write/Bash vs ApplyPatch/run_terminal_cmd | 100% |
| L3 特有短语 | "CLAUDE.md" / "multi_tool_use.parallel" | 95% |
| L4 目录指纹 | .claude/ vs .codex/ vs .kiro/ | 90% |
| L5-L10 | 消息格式/二进制/API 端点 | 80-90% |
| L11-L20 | 流协议/推理架构/权限系统/沙箱/遥测 | 70-85% |

详见 `ROUTING_FEATURES.md` 和 `ROUTING_DEEP_FEATURES.md`。

---

## 当前状态

- Claude Code / Cursor / Kiro / Codex 已接入
- Round 11 训练中（2387 条，含真实 IDE 提示词 + HuggingFace 数据）
- 20 层 IDE 识别特征已整理
- 三层路由 + Fallback 架构已设计
- 熔断器 + 同层降级 + 跨层升级保护
- UI 后台显示 IP/国家/IDE/协议/能力

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
