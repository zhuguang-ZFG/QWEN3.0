# LiMa — 多模型智能路由 AI 编程助手后端

> **M-OC0**: LiMa CLI migrated to OpenCode MCP bridge. `lima-code` → `lima`. See `docs/opencode-integration.md`.

> **个人 AI 编程助手** — OpenAI-compatible API，自动路由到最优后端模型

LiMa 是一个**多模型智能路由后端**，提供 `/v1/chat/completions` 和 `/v1/messages` 端点，根据请求意图、能力、成本和质量自动选择最优后端模型。客户端包括 OpenCode、Cursor、VS Code Copilot、Telegram 及自定义 CLI。

## 核心能力

| 能力 | 说明 |
|---|---|
| **多模型路由** | 根据意图/能力/成本/质量自动选择最优模型（180+ 后端） |
| **OpenCode 深度适配** | overflow 检测、消息规范化、usage 跟踪、reasoning_effort 透传 |
| **代码读写** | 代码文件读取、分析、Bug 修复、重构 |
| **工具调用** | 原生 OpenAI tool_calls + 文本提取式工具调用 |
| **联网搜索** | SCNet / Kimi-search 实时联网 |
| **会话亲和** | x-session-affinity sticky session |
| **健康监控** | 自动健康检查 + 后端降级 |

## 架构

```
┌─ 用户 ──────────────────────────────────────────────┐
│  OpenCode / Cursor / VS Code / Telegram              │
└──────────────┬──────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────┐
│  LiMa Router (port 8080, VPS, FastAPI)               │
│  ├─ routing_engine.py     智能路由决策                │
│  ├─ opencode_config.py    OpenCode IDE 配置中心       │
│  ├─ opencode_error_adapter.py  Overflow 检测          │
│  ├─ opencode_message_normalizer.py  消息规范化        │
│  ├─ code_orchestrator.py  代码上下文注入              │
│  └─ skills_injector.py    后端感知 skill 注入         │
└──────┬──────┬──────┬──────┬──────────────────────────┘
       ▼      ▼      ▼      ▼
┌──────┐ ┌────┐ ┌────┐ ┌────────┐
│SCNet │ │Kimi│ │MiMo│ │LongCat │  ← 180+ 云端后端
└──────┘ └────┘ └────┘ └────────┘
```

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zhuguang-ZFG/QWEN3.0.git
cd QWEN3.0

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API keys

# 3. 启动
pip install -r requirements_server.txt
python server.py

# 4. 测试
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{"model":"lima-1.3","messages":[{"role":"user","content":"写一个快速排序"}]}'
```

### OpenCode 配置

在项目根目录创建 `.lima/settings.json`：

```json
{
  "env": {
    "BASE_URL": "https://your-domain.com/v1",
    "MODEL": "lima-1.3"
  }
}
```

## 可用模型

| 后端 | 模型 | 联网 | 工具调用 | 上下文 |
|---|---|---|---|---|
| SCNet | deepseek-v4-flash/pro, qwen3-30b/235b | ✅ | ✅ | 500K |
| Kimi | kimi, kimi-thinking, kimi-search | ✅ | ✅ | 平台限制 |
| MiMo | mimo-web, mimo-web-think, mimo-v3-pro | ❌ | ✅ | 平台限制 |
| LongCat | longcat-web, longcat-web-think | ❌ | ✅ | 平台限制 |
| Cloudflare | gpt-4o-mini, llama4, deepseek-r1 等 37+ | ❌ | ✅ | API 限制 |

## 项目结构

```
lima-router/
├── server.py                   # FastAPI 入口
├── routing_engine.py           # 路由引擎（5层：分类→选择→注入→执行→响应）
├── routing_executor.py         # 路由执行（fallback 链）
├── routing_selector.py         # 后端选择（健康/粘性/预算）
├── backends_registry.py        # 后端注册表（180+ 提供商）
├── opencode_config.py          # OpenCode IDE 配置中心
├── opencode_error_adapter.py   # Overflow 检测 + 错误响应构建
├── opencode_message_normalizer.py  # 消息规范化管线
├── http_caller.py              # HTTP 传输层（sync/async/stream）
├── chat_models.py              # 请求模型（含 reasoning_effort）
├── routes/
│   ├── chat_endpoints.py       # OpenAI/Anthropic 协议端点
│   ├── chat_handler.py         # 对话处理（含 413 overflow 响应）
│   ├── chat_stream.py          # SSE 流式生成
│   └── v3_adapters.py          # 后端适配层
├── context_pipeline/           # 上下文管道（检索/搜索/代码/压缩）
├── session_memory/             # 会话记忆（SQLite）
├── deploy_opencode.py          # OpenCode 部署脚本
└── docs/                       # 文档
```

## 部署

```bash
# Docker
docker compose build && docker compose up -d

# VPS 部署
python deploy_opencode.py

# 健康检查
curl -sf https://your-domain.com/health
```

详细部署文档见 [`AGENTS.md`](AGENTS.md)。

## 许可

MIT
