# AGENTS_CN.md

本文件为 Qoder (qoder.com) 在本仓库中工作时提供指导。

## 项目概述

LiMa 是一个多后端 AI 路由服务器（Python 3.10 + FastAPI），提供 OpenAI/Anthropic 兼容的 API。它根据请求类型、健康状况、预算和质量评分，智能地将请求路由到 170 多个 AI 后端（Groq、NVIDIA、OpenRouter、DeepSeek、Cloudflare 等）。目前正从“个人编码助手”转型为“AI 智能设备云服务”。

**公共端点：** `https://chat.donglicao.com`（VPS nginx → :8080）

## 常用命令

```powershell
# 运行所有测试
python -m pytest --tb=short -q

# 运行单个测试文件
python -m pytest tests/test_routing_engine.py -v

# 按名称运行单个测试
python -m pytest tests/test_routing_engine.py -k "test_classify_ide" -v

# 完整 CI 风格测试（忽略长时间/外部测试）
python scripts/run_pre_commit_check.py --full

# 代码检查
ruff check .

# 格式检查/自动格式化
ruff format --check
ruff format .

# 类型检查（特定文件）
pyright server.py routing_engine.py

# 本地启动服务器
python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Docker
docker compose build
docker compose up -d

# 冒烟测试（本地）
curl -sf http://127.0.0.1:8080/health

# 部署到 VPS
python scripts/deploy_unified.py

# 仓库统计
python scripts/repo_stats.py
```

## 架构

### 请求管道（生产环境）

```
客户端 → server.py (BodySizeLimitMiddleware, access_guard)
      → routes/chat_endpoints.py | routes/anthropic_messages_handler.py
      → routes/chat_preflight.py (防护栏、预算、身份)
      → routing_engine.route()          ← 权威路由入口
         ├─ identity_guard              (身份短路)
         ├─ semantic_cache              (缓存命中短路)
         ├─ routing_classifier.classify (请求类型: ide/chat/code/image)
         ├─ routing_classifier.classify_scenario (场景: coding/chat/device/...)
         ├─ skill_store recall          (技能记忆 → recalled_backend)
         ├─ context_pipeline.retrieval_injection (知识图谱/向量上下文)
         ├─ code_context_injection      (仅编码: tree-sitter 扫描)
         ├─ router_v3.select_backends → routing_selector.select (后端排名)
         ├─ skills_injector             (将技能注入消息)
         ├─ speculative                 (简单请求: 并行投机调用)
         ├─ routing_executor.execute    (顺序/并行 + 回退)
         ├─ response_validator          (编码: 质量验证 + 重试)
         └─ route_post_process          (关联/证据/反馈)
      → http_caller → 后端池 (httpx 同步/异步/流)
      → routes/chat_post_closeout.py (内存、指标、蒸馏队列)
      → 客户端 (JSON 或 SSE)
```

权威文档: `docs/REQUEST_PIPELINE_AUTHORITY.md`

### 关键模块职责

| 关注点 | 模块 | 遗留/外观 |
|--------|------|-----------|
| 后端注册 | `backends_registry.py` + `backends_constants.py` | `backends.py` 重导出 |
| 意图分类 | `routing_classifier.py` | `smart_router.classify` |
| 后端池 | `router_v3.py` (`POOLS` 字典) | — |
| 后端排名 | `routing_selector.py` | — |
| 后端执行 | `routing_executor.py` | — |
| HTTP 传输 | `http_caller.py` (→ `http_sync`/`http_async`/`http_stream`) | `router_http.py` (urllib) |
| 健康/冷却 | `health_tracker.py` | `router_circuit_breaker.py` |
| 预算 | `budget_manager.py` | — |
| 粘性会话 | `sticky_session.py` | — |
| 流桥接 | `streaming.py`, `routes/stream_handlers.py` | — |
| 检索注入 | `context_pipeline/retrieval_injection.py` | — |
| 代码上下文 | `context_pipeline/code_context_injection.py` | — |
| 技能注入 | `skills_injector.py` | — |
| 语义缓存 | `semantic_cache.py` | — |
| 会话内存 | `session_memory/store*.py` (拆分: db/crud/promote/admin) | — |
| 质量门 | `routes/quality_gate*.py` | 根 `quality_gate.py` (编码评估) |
| 代理任务 | `routes/agent_tasks.py` + `agent_runtime/` | — |
| 运维指标 | `routes/ops_metrics.py` | — |

### 并行子系统（非聊天热路径）

| 子系统 | 路径 | 用途 |
|--------|------|------|
| 设备网关 | `device_gateway/`, `routes/device_gateway*.py` | `/device/v1/*`; Redis 任务队列 + WSS; ESP32/硬件 |
| 渠道网关 | `channel_gateway/`, `routes/channel_gateway.py` | 斜杠命令, G3 会话 |
| 代理运行时 | `agent_runtime/` | LiMa Code 任务编排 |
| 会话内存 | `session_memory/` | 持久内存 + 学习循环 |
| 上下文管道 | `context_pipeline/` (43 个模块) | 检索、代码上下文、验证、重排序 |
| 可观测性 | `observability/` | Prometheus 指标、结构化日志 |
| 提供商探测 | `provider_probe/`, `provider_automation/`, `backends_registry/` | 自动发现新 AI 提供商 |

### 服务器启动

- `server.py` — 轻量 FastAPI 入口；连接中间件，注入依赖，通过 `routes/route_registry.py` 注册路由
- `server_bootstrap.py` — 模型常量 (`MODEL_ID = "lima-1.3"`), 运行时状态, Cloudflare 最后手段回退
- `server_lifespan.py` — 异步生命周期：加载健康状态、后端配置、启动探测循环、编码评估、会话内存守护进程、MQTT、Prometheus 导出器、自动索引器
- `smart_router.py` — **遗留外观**；新代码直接从底层模块导入

### 部署拓扑

```
互联网 → VPS (nginx → lima-router :8080, Redis)
              ↕ FRP :8088
         Windows 本地 (:8080 开发代理 + 免费后端)
```

- 主 VPS: `47.112.162.80` (阿里云)
- 次节点: 京东云 `117.72.118.95` (仅提供商探测/监控)
- 部署脚本: `scripts/deploy_unified.py` (容量感知, 自动备份)
- 回滚: `/opt/lima-router/backups/`

## 技术栈

- **运行时:** Python 3.10 + FastAPI + uvicorn
- **HTTP 客户端:** httpx (替代遗留 urllib in `router_http.py`)
- **数据:** SQLite (语义缓存, 会话内存), Redis (设备任务)
- **断路器:** pybreaker
- **代码检查:** ruff (配置 in `ruff.toml`, 目标 py310, 行长度 120)
- **类型检查:** pyright
- **测试:** pytest (asyncio_mode=auto, testpaths=tests)
- **容器:** Docker 多阶段 (python:3.10-slim)

## 代码质量规则

### 硬性规则 (Superpowers)

1. **禁止静默降级** — 在生产路径中不允许 `except Exception: pass` 或 `except ImportError: pass`。必须至少 `logger.warning` 并说明原因。关键依赖 (chromadb, tree-sitter) 必须在启动时记录清晰警告，而不是在运行时静默降级。
2. **禁止自动降级验证** — VPS 部署必须在真实 VPS 上验证，而不仅仅是 localhost。公共 API 必须通过真实域名和真实令牌测试。
3. **.env 合并，而非覆盖** — 部署必须先备份 VPS `.env`，然后追加新变量，绝不 `sftp.put` 覆盖。
4. **Telegram 已退役** — 不要重新注册 `/telegram` 路由、webhooks 或出站通知。

### 尺寸约束

- 单文件目标: ≤300 行
- 单函数目标: ≤50 行
- 超过 300 行的新模块必须拆分

### 新代码不应使用的模块

| 模块 | 状态 |
|------|------|
| `smart_router.py` 聊天路径 | 遗留外观；使用 `routing_engine.route()` |
| `router_http.py` 直接调用 | 遗留 urllib；使用 `http_caller` |
| `context_pipeline.factory` 作为唯一管道 | 仅限实验室/测试工具 |

## 开发工作流

```
1. 设计文档 (docs/*.md) 用于非琐碎更改
2. 本地编码
3. pytest (专注 → 完整 用于生产更改)
4. ruff check + pyright 在修改的文件上
5. VPS 部署 + 健康/冒烟验证 (scripts/deploy_unified.py)
6. 更新 STATUS.md / progress.md / findings.md
7. git commit (约定式, 仅里程碑文件) → push origin → push gitee
```

## Git 规则

- **绝不** 使用 `git add .` — 仅暂存与里程碑相关的文件
- 不要暂存 `.claude/`, 参考仓库, 临时调试脚本, 凭证, `.env`, `.lima-data/`
- 不要提交真实密钥、VPS 密码或 API 令牌
- 没有明确用户许可不要强制推送或重置
- 工作区可能包含用户更改；不要随意 `git reset` 或 `git checkout`

## 里程碑协作协议

1. 所有者实现里程碑切片
2. 代理审查代码，运行专注测试 → 完整测试 → `git diff --check`
3. 代理使用关闭证据更新 `progress.md` / `findings.md`
4. 代理仅暂存相关文件，提交（约定式），推送到 GitHub (`origin`) + Gitee (`gitee`)
5. 只有在推送后代理才提议下一个里程碑

**自动关闭**（当用户没有说“不要部署/提交”时）：本地 pytest → VPS 部署 + 重启 + 健康/冒烟 → 更新文档 → git add/commit/push。

## 关键文档

| 文档 | 用途 |
|------|------|
| `STATUS.md` | 当前项目状态 |
| `CLAUDE.md` | 精简开发规则 + 仓库统计 |
| `docs/REQUEST_PIPELINE_AUTHORITY.md` | 18 步管道 + 模块职责矩阵 |
| `docs/ROUTING_ENGINE_DESIGN.md` | routing_engine.py 设计决策 |
| `docs/TECHNICAL_ARCHITECTURE.md` | 完整架构（注意：某些部分过时） |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署/发布硬性规则 |
| `docs/LIMA_MEMORY.md` | 长期项目记忆 |
| `docs/PERSONAL_CODING_ASSISTANT_PLAN.md` | 当前主要计划 |
| `task_plan.md` | 当前任务计划 + 证据 |
| `findings.md` | 事实发现和运维结论 |
| `progress.md` | 执行进度日志 |

## 环境变量

参见 `.env.example` 获取完整列表。关键变量：

- `LIMA_API_KEY` / `LIMA_API_KEYS` — 必需，缺少时服务器报错
- `LIMA_ADMIN_TOKEN` — 管理面板认证
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — 核弹级回退后端
- `LIMA_DEPLOY_PASS` — VPS 部署密码
- 功能标志默认关闭: `GITEE_WEBHOOK_ENABLED=0`, `GITHUB_WEBHOOK_ENABLED=0`, `SEARXNG_ENABLED=0`, `CODESEARCH_MCP_ENABLED=0`, 等。