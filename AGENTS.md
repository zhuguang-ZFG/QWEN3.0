# AGENTS.md

本文件为 AI Agent 提供本项目（donglicao.com）的操作指南。

---

## 项目概述

LiMa 是一个多后端 AI 路由服务器（Python 3.10 + FastAPI），提供兼容 OpenAI 的 API。它根据请求类型、健康状态、预算和质量评分，智能路由到 170+ 个 AI 后端（Groq、NVIDIA、OpenRouter、DeepSeek、Cloudflare 等）。同时作为 AI 绘画/写作/数字人设备（基于 ESP32 的智能硬件）的云平台。

**公网入口：** `https://chat.donglicao.com`（VPS nginx → :8080）

---

## 常用命令

```powershell
# 运行全部测试
python -m pytest --tb=short -q

# 运行单个测试文件
python -m pytest tests/test_routing_engine.py -v

# 按名称运行单个测试
python -m pytest tests/test_routing_engine.py -k "test_classify_ide" -v

# 完整 CI 风格测试（跳过长耗时/外部测试）
python scripts/run_pre_commit_check.py --full

# 代码检查
ruff check .

# 格式检查 / 自动格式化
ruff format --check
ruff format .

# 类型检查（指定文件）
pyright server.py routing_engine.py

# 本地启动服务
python -m uvicorn server:app --host 0.0.0.0 --port 8080

# Docker
docker compose build
docker compose up -d

# 冒烟测试（本地）
curl -sf http://127.0.0.1:8080/health

# 部署到 VPS（core 切片包含后端运行时与静态资源）
python scripts/deploy_unified.py --slice core

# 部署 Chat Web 静态文件到 VPS
python scripts/deploy_chat_web.py

# 仓库统计
python scripts/repo_stats.py
```

### 小程序一键上传（微信开发者工具 CLI）

```bash
# 1. 进入小程序目录
cd esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile

# 2. type check（确保 0 errors）
npx vue-tsc --noEmit

# 3. 编译（mp-weixin）
npx uni build --platform mp-weixin

# 4. 一键上传到微信平台
"/c/Users/zhugu/微信web开发者工具/cli.bat" upload \
  --project "$(pwd)/dist/build/mp-weixin" \
  --v "X.Y.Z" \
  -d "提交说明"

# 5. 提交版本号 + 推送
#    manifest.config.ts: versionName / versionCode +1
git add manifest.config.ts src/manifest.json src/pages.json
git commit -m "chore: bump version to X.Y.Z"
git push origin main

# 6. 父仓库更新子模块指针
cd /d/QWEN3.0
git add esp32S_XYZ
git commit -m "chore: bump esp32S_XYZ submodule — mini-program vX.Y.Z uploaded"
git push origin main
```

**注意事项**：
- AppID：`wxbf3c1e0013b46343`（已配置在 `env/.env` 和 `manifest.config.ts`）
- 版本号递增：每次上传前 bump `versionName`（如 `3.6.0`→`3.6.1`）和 `versionCode`（`360`→`361`）
- 上传后需要在 [mp.weixin.qq.com](https://mp.weixin.qq.com) 提交审核才能发布
- 微信开发者工具需提前登录并开启「设置 → 安全设置 → 服务端口」

---

## 架构

### 请求处理流水线（生产环境）

```
Client → server.py (BodySizeLimitMiddleware, access_guard)
      → routes/chat_endpoints.py
      → routes/chat_preflight.py (guardrails, budget, identity)
      → routing_engine.route()          ← 权威路由入口
         ├─ identity_guard              (身份短路)
         ├─ routing_classifier.classify (request_type: ide/chat/vision)
         ├─ routing_classifier.classify_scenario (scenario: coding/chat)
         ├─ skill_store recall          (技能记忆 → 召回后端)
         ├─ context_pipeline.retrieval_injection (知识图谱/向量上下文，按需)
         ├─ router_v3.select_backends → routing_selector.select (后端排序)
         ├─ skills_injector             (向消息注入技能)
         ├─ speculative                 (简单请求：并行推测调用)
         ├─ routing_executor.execute    (串行/并行 + 降级)
         └─ route_post_process          (关联/证据/反馈)
      → http_caller → backend pool (httpx sync/async/stream)
      → routes/chat_post_closeout.py (记忆、指标、蒸馏队列)
      → Client (JSON 或 SSE)
```

权威文档：`docs/REQUEST_PIPELINE_AUTHORITY_CN.md`（中文权威版；英文归档已删除）

### 关键模块归属

| 职责 | 模块 | 遗留/门面 |
|------|------|-----------|
| 后端注册 | `backends_registry/` 包 + `backends_constants.py` | — |
| 意图分析 | `routing_intent.py` | — |
| 意图分类 | `routing_classifier.py` | — |
| 后端池 | `router_v3/` 包 (`POOLS` 在 `pools.py`) | — |
| 后端排序 | `routing_selector/` 包 | — |
| 后端执行 | `routing_executor.py` | — |
| HTTP 传输 | `http_caller.py` (→ `http_sync`/`http_async`/`http_stream`) | — |
| 健康/冷却 | `health_tracker.py` | — |
| 预算 | `budget_manager.py` | — |
| 粘性会话 | `sticky_session.py` | — |
| 流桥接 | `streaming.py`, `routes/stream_handlers.py` | — |
| 检索注入 | `context_pipeline/retrieval_injection.py` | — |
| 代码上下文 | `context_pipeline/code_context_injection.py` | 已标记 `DEPRECATED v3.0`（编码能力退役） |
| 技能注入 | `skills_injector.py` | — |
| 会话记忆 | `session_memory/store*.py` (拆分：db/crud/promote/admin) | — |
| 运维指标 | `routes/ops_metrics.py` | — |

### 并行子系统（非聊天主路径）

| 子系统 | 路径 | 用途 |
|--------|------|------|
| 设备网关 | `device_gateway/`, `routes/device_gateway*.py` | `/device/v1/*`；Redis 任务队列 + WSS；ESP32/硬件 |

| 会话记忆 | `session_memory/` | 持久记忆 + 学习循环 |
| 上下文流水线 | `context_pipeline/` (17 模块) | 检索注入、技能记忆、响应验证/重排序、token 预算、路由权重（代码上下文 v3.0 已退役移除） |
| 可观测性 | `observability/` | Prometheus 指标、结构化日志 |
| 提供商探测 | `packages/provider-probe-offline/provider_probe/`（冷离线；根目录 `provider_probe/` 为指针）, `provider_automation/`, `backends_registry/` | 自动发现新 AI 提供商（仅 JDCloud） |

### 服务启动

- `server.py` — 精简 FastAPI 入口；连接中间件、注入依赖、通过 `routes/route_registry.py` 注册路由
- `server_bootstrap.py` — 模型常量 (`MODEL_ID = "lima-1.3"`)、运行时状态、Cloudflare 终极降级
- `server_lifespan.py` — 异步生命周期：加载健康状态、后端画像、启动探测循环、会话记忆守护进程、MQTT、Prometheus 导出器、自动索引器

### 部署拓扑

```
Internet → VPS (nginx → lima-router :8080, Redis)
              ↕ FRP :8088
         Windows 本地 (:8080 开发代理 + 免费后端)
```

- 主 VPS：`47.112.162.80`（阿里云）
- 备用节点：JDCloud `117.72.118.95`（仅提供商探测/监控）
- 部署脚本：`scripts/deploy_unified.py`（容量感知、自动备份）
- 回滚：`/opt/lima-router/backups/`

---

## 技术栈

- **运行时：** Python 3.10 + FastAPI + uvicorn
- **HTTP 客户端：** httpx
- **数据：** SQLite（语义缓存、会话记忆），Redis（设备任务）
- **代码检查：** ruff（配置在 `ruff.toml`，目标 py310，行宽 120）
- **类型检查：** pyright
- **测试：** pytest（asyncio_mode=auto，testpaths=tests）
- **容器：** Docker 多阶段（python:3.10-slim）

---

## 代码质量规则

### 硬规则（不可违反）

1. **禁止静默降级** — 生产路径中禁止使用 `except Exception: pass` 或 `except ImportError: pass`。至少必须 `logger.warning` 并说明原因。关键依赖（chromadb、tree-sitter）必须在启动时记录清晰警告，而非在运行时静默降级。
2. **禁止自动降级验证** — VPS 部署必须在真实 VPS 上验证，不能仅在 localhost 上验证。公网 API 必须通过真实域名和真实 token 测试。
3. **.env 合并而非覆盖** — 部署必须先备份 VPS 的 `.env`，追加新变量，绝不能用 `sftp.put` 覆盖。
4. **Telegram 通知通道已退役** — 不要重新注册 `/telegram` 路由、webhook 或出站通知。注意：Telegram Bot API 仍作为 gallery 图片存储后端使用（`integrations/telegram_bot/`，见 `routes/device_app_gallery.py`），这不是通知通道，不要误删。

### 文档语言

- **文档类产物必须使用中文**：新增或更新 `docs/**/*.md`、根部说明文档、计划、状态、进展、报告、runbook、PRD、架构说明和交接文档时，默认使用中文撰写。
- 保留必要的英文代码标识、命令、API 字段、日志片段、协议字段、文件名、路径、提交信息和外部专有名词。
- 如果修改既有英文文档，不要求一次性全文翻译，但本次新增段落和后续文档类增量必须优先使用中文。

### 大小约束

- 单文件目标：≤300 行
- 单函数目标：≤50 行
- 超过 300 行的新模块必须拆分

### 新代码禁止使用的模块

| 模块 | 状态 |
|------|------|
| `context_pipeline.factory` 作为唯一流水线 | 仅实验室/测试工具使用 |

---

## 开发流程

```
1. 设计文档（docs/*.md）用于非平凡变更
2. 本地编码
3. pytest（聚焦 → 完整用于生产变更）
4. ruff check + pyright 针对修改的文件
5. VPS 部署 + 健康/冒烟验证（scripts/deploy_unified.py）
6. 更新 STATUS.md / progress.md / findings.md
7. git commit（conventional，仅里程碑文件）→ push origin（GitHub）
   - **Gitee 镜像已退役**：不再维护 `gitee` remote，不再双推。历史提交保留在 GitHub。
```

## Git 规则

- **禁止** 使用 `git add .` — 仅暂存与里程碑相关的文件
- 禁止暂存 `.claude/`、参考仓库、临时调试脚本、凭证、`.env`、`.lima-data/`
- 禁止提交真实密钥、VPS 密码或 API token
- 禁止在未经用户明确许可的情况下 force-push 或 reset
- 工作区可能包含用户更改；不要随意 `git reset` 或 `git checkout`

## 里程碑协作协议

1. 用户实现里程碑切片
2. Agent 审查代码，运行聚焦测试 → 完整测试 → `git diff --check`
3. Agent 更新 `progress.md` / `findings.md` 并附上结项证据
4. Agent 仅暂存相关文件，提交（conventional），推送到 GitHub（`origin`）
5. 仅在推送后，Agent 才提议下一个里程碑

**自动结项**（当用户未说"不要部署/提交"时）：本地 pytest → VPS 部署 + 重启 + 健康/冒烟 → 更新文档 → git add/commit/push。

**小程序改动**：当 `esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/` 下有代码变更时，自动执行「小程序一键上传」流程（见上文「常用命令」），包括编译、上传、版本号 bump、子模块指针提交推送。

## ECC 开发流程（增量采用）

> 参考跨 harness 工程实践（Everything Claude Code，本地副本位于 `.claude/ecc/`），按 LiMa 现状做增量裁剪。ECC 流程优先于通用建议，但低于本文件「硬规则」和用户的直接指令。

核心要求：

1. **先计划**：非平凡改动先计划，用户批准后执行。
2. **TDD**：RED → GREEN → REFACTOR；提交前 focused → full tests。
3. **代码审查**：自查无 secret、输入验证、错误不泄露、无静默吞异常、小文件/小函数、优先不可变。
4. **提交前**：`ruff`、`pyright`、`scripts/check_code_size.py`、文档同步、仅暂存相关文件、conventional commits。
5. **安全响应**：STOP → 修复 CRITICAL → 轮换 secret → 检查同类问题 → 更新 `findings.md`。

完整清单见 [`docs/ECC_WORKFLOW_CN.md`](docs/ECC_WORKFLOW_CN.md)。

---

## 关键文档

| 文档 | 用途 |
|------|------|
| `STATUS.md` | 当前项目状态 |
| `CLAUDE.md` | 精简开发规则 + 仓库统计 |
| `docs/REQUEST_PIPELINE_AUTHORITY_CN.md` | 18 步流水线 + 模块归属矩阵 |
| `docs/archive/ROUTING_ENGINE_DESIGN.md` | routing_engine.py 设计决策（已归档） |
| `docs/ARCHITECTURE.md` | 系统架构 |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署/发布硬规则 |
| `docs/LIMA_MEMORY_CN.md` | 长期项目记忆 |
| `docs/superpowers/specs/2026-07-02-system-slimdown-design.md` | 当前瘦身/优化计划（旧的战略规划已归档至 `docs/archive/strategic-plans-2026-06/`） |
| `docs/archive/task_plan.md` | 历史任务计划（已归档） |
| `findings.md` | 事实发现和运维结论 |
| `progress.md` | 执行进度日志 |

## 环境变量

详见 `.env.example`。关键项：

- `LIMA_API_KEY` / `LIMA_API_KEYS` — 必需，缺失时服务器报错
- `LIMA_ADMIN_TOKEN` — 管理面板认证
- `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_TOKEN` — 核降级后端
- `LIMA_DEPLOY_PASS` — VPS 部署密码
- 功能标志默认关闭：`SEARXNG_ENABLED=0`、`CODESEARCH_MCP_ENABLED=0` 等（已退役的 GitHub/Gitee webhook 变量已从 `.env.example` 移除）

## CodeGraph — 代码智能（优先于 GitNexus）

本仓库使用 **CodeGraph** 进行调用图探索、影响分析和死代码审计。索引位于 `.codegraph/codegraph.db`。**禁止**在此使用 GitNexus hooks 或 `gitnexus_*` MCP 工具。

### 必须做的事

- 拉取或大规模重构后：`codegraph sync .`（或如果缺失则 `codegraph index .`）
- 编辑不熟悉的符号前：CodeGraph MCP 或 `codegraph impact <symbol>`
- 删除模块前：`python scripts/codegraph_orphans.py --fanin`（图 + ripgrep；仅图检测出的孤儿可能是惰性导入）

### 设置

| 任务 | 命令 |
|------|------|
| 所有本地 Agent 的 MCP | `pwsh -File scripts/setup_codegraph_agents.ps1` |
| LiMa MCP 包（codegraph + context7 + fetch） | `pwsh -File scripts/setup_lima_mcps.ps1` |
| 项目索引 | `codegraph index .` 然后 `codegraph sync .` |

### 参考

- 孤儿审计：`scripts/codegraph_orphans.py`
- 瘦身证据：`progress.md`（2026-06-15 CodeGraph 条目）

## Ponytail（顾问规则，LiMa 优先）

本项目采用 [Ponytail](https://github.com/DietrichGebert/ponytail) 的「lazy senior dev」理念作为代码精简顾问。详情见 [`docs/AGENTS_PONYTAIL.md`](docs/AGENTS_PONYTAIL.md)（上游仓库见 GitHub 链接，本地未留存源文件）。

### 新增代码/提交前自问（Ponytail 阶梯）

1. 这个功能真的需要吗？（YAGNI）
2. Python 标准库能直接做到吗？
3. 平台/框架原生特性能直接做到吗？
4. 已有依赖能直接做到吗？
5. 能一行写完吗？
6. 最后才写最小实现。

### 不可删除的边界

- 信任边界的输入验证（`access_guard.py`、`identity_guard.py`）
- 防数据丢失的错误处理（`session_memory/` 持久化逻辑）
- 安全措施（白/黑名单、secret 保护、无静默降级）
- 测试门禁（`pytest`、`ruff check .`、`pyright`、`scripts/check_code_size.py`）
- 文档同步（`STATUS.md` / `progress.md` / `findings.md`）

### 简化标记

如果使用 Ponytail 建议的捷径，且该捷径有已知上限（全局锁、O(n²) 扫描、朴素启发式），用 `ponytail:` 注释说明上限和升级路径，并记入 `PONYTAIL-DEBT.md`。
