# LiMa 基础设施 (infra/)

## 概述

LiMa 本地基础设施代码，包含 Cloudflare Worker 代理、本地服务管理、健康监控等。
部署于 Windows 11 本地机器 (RTX 5060 Ti 16GB) + Cloudflare Workers。

---

## 文件说明

### 1. scnet-worker.js — 国家超算互联网平台代理

**功能：** 将 scnet.cn 的免费 AI 服务转为 OpenAI 兼容 API

**支持模型（5个，全部免费，无需登录/Key）：**

| 模型名 | modelId | 说明 |
|--------|---------|------|
| qwen3-30b | 17 | Qwen3-30B，轻量专家模型 |
| minimax-m2.5 | 410 | MiniMax M2.5，编程能力强 |
| qwen3-235b | 120 | Qwen3-235B，顶级专家模型 |
| deepseek-v4-flash | 520 | DeepSeek-V4-Flash，高效 |
| deepseek-v4-pro | 510 | DeepSeek-V4-Pro，工程级 |

**部署：** CF Worker → `scnet.zhuguang.ccwu.cc`

**限制：** 单次输入最大 5 万字符。LiMa 主服务端 (smart_router.py) 自动分段突破此限制。

---

### 2. lima-startup.bat — 开机自启动脚本

**功能：** Windows 开机后自动启动所有本地 AI 服务

**管理的服务：**
- Ollama (GPU 推理, port 11434)
- DuckAI (port 4500)
- TheOldLLM proxy (port 4502)
- g4f API server (port 4503)

**注册方式：** Task Scheduler `LiMa-Startup`，开机 30 秒后执行

---

### 3. lima-health.bat — 健康监控 + 自动恢复

**功能：** 每 5 分钟检测所有服务，挂了自动重启

**监控项：**
- Ollama (port 11434) — 自动重启
- DuckAI (port 4500) — 自动重启
- TheOldLLM (port 4502) — 自动重启
- g4f (port 4503) — 自动重启
- Cloudflared — 自动重启 Windows 服务
- 代理 7897 — 仅检测告警

**日志：** `D:\ollama_server\health.log`
**注册方式：** Task Scheduler `LiMa-HealthCheck`，每 5 分钟

---

### 4. g4f_server.py — g4f API 服务器启动器

**功能：** 设置代理环境变量后启动 g4f OpenAI 兼容 API

**可用模型 (via PollinationsAI)：**
- openai (GPT-4o-mini)
- openai-large (GPT-4o)
- deepseek (DeepSeek V3)
- qwen-coder (Qwen Coder)

**端口：** 4503

---

### 5. heckai-worker.js — heck.ai 代理 (实验性)

**状态：** 部署成功但 heck.ai 对代理 IP 做了限制，暂不可用。
保留代码供后续 IP 解封后使用。
