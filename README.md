# LiMa Code CLI

> **个人 AI 编程助手** — 对标 Claude Code / OpenAI Codex

LiMa 是一个**多模型智能路由 AI 编程助手**，通过反向工程免费 AI 平台提供编码能力。
支持代码阅读、分析、修改，通过 CLI / VS Code / Telegram 交互。

## 核心能力

| 能力 | 说明 |
|---|---|
| **多模型路由** | 根据意图/能力/成本/质量自动选择最优模型 |
| **逆向后端** | 集成 SCNet、Kimi、MiMo、LongCat 等免费 AI 平台 |
| **代码读写** | 代码文件读取、分析、Bug 修复、重构 |
| **长上下文** | SCNet OSS 文件桥接支持 500K 字符 |
| **工具调用** | 文本提取式工具调用（Kimi 已验证） |
| **联网搜索** | SCNet / Kimi-search 实时联网 |
| **健康监控** | 4 代理自动健康检查 + Cookie 过期告警 |

## 架构

```
┌─ 用户 ──────────────────────────────────────┐
│  CLI (deepcode-cli) / VS Code / Telegram     │
└──────────────┬───────────────────────────────┘
               ▼
┌──────────────────────────────────────────────┐
│  LiMa Router (port 8080, VPS)                │
│  ├─ routing_engine.py   智能路由决策          │
│  ├─ tool_forward.py     工具调用转发          │
│  ├─ code_orchestrator   代码上下文注入         │
│  └─ text_tool_extractor 文本工具提取           │
└──────┬──────┬──────┬──────┬──────────────────┘
       ▼      ▼      ▼      ▼
┌──────┐ ┌────┐ ┌────┐ ┌────────┐
│SCNet │ │Kimi│ │MiMo│ │LongCat │  ← 逆向后端
│:4505 │ │:4504│ │:4507│ │:4506  │     (VPS)
└──┬───┘ └─┬──┘ └─┬──┘ └───┬────┘
   ▼       ▼     ▼        ▼
 国家算力  moonshot 小米  longcat
 平台      .cn     AI    .chat
```

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/zhuguang-ZFG/QWEN3.0.git
cd QWEN3.0

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API keys

# 3. 启动（本地）
pip install -r requirements_server.txt
python server.py

# 4. 测试
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"写一个快速排序"}]}'
```

## 可用模型

| 后端 | 模型 | 联网 | 工具调用 | 上下文 |
|---|---|---|---|---|
| SCNet | deepseek-v4-flash/pro, qwen3-30b/235b, minimax-m2.5 | ✅ | ❌ | 500K |
| Kimi | kimi, kimi-thinking, kimi-search | ✅ | ✅ (文本) | 平台限制 |
| MiMo | mimo-web, mimo-web-think, mimo-web-flash | ❌ | ✅ (文本) | 平台限制 |
| LongCat | longcat-web, longcat-web-think | ❌ | ✅ (文本) | 平台限制 |
| Cloudflare | gpt-4o-mini, llama4, deepseek-r1 等 37+ | ❌ | ✅ | API 限制 |

## 项目结构

```
lima-router/
├── router_v3.py          # 主路由引擎
├── routing_engine.py     # 路由决策
├── routes/               # API 路由
│   ├── chat_handler.py   # 对话处理
│   ├── tool_forward.py   # 工具调用转发
│   └── reverse_gateway.py # 逆向后端管理
├── reverse_gateway/      # 逆向后端适配器
│   ├── providers/
│   │   ├── scnet.py      # SCNet Web Chat 适配器
│   │   ├── scnet_adapter.py
│   │   ├── scnet_protocol.py
│   │   └── scnet_file_context.py  # OSS 文件桥接
│   └── sidecar_scnet.py  # SCNet Sidecar
├── code_orchestrator.py  # 代码编排
├── text_tool_extractor.py # 文本工具提取
├── infra/                # 代理脚本
│   ├── kimi_proxy_v2.js  # Kimi 代理
│   ├── scnet_large_proxy.js
│   └── scnet-worker.js
├── scripts/              # 运维脚本
│   ├── reverse_proxy_keepalive.py  # 健康监控
│   ├── provision_kimi_cookies.py
│   └── provision_scnet_cookies.py
├── deploy/reverse/       # Sidecar 部署配置
└── docs/                 # 文档
```

## 部署

VPS 部署文档见 [`deploy/reverse/README.md`](deploy/reverse/README.md)。

## 许可

MIT
