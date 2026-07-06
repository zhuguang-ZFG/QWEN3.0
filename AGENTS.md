# AGENTS.md

本文件为 AI Agent 提供本项目（donglicao.com）的操作指南。

---

## 项目概述

DLC 绘图服务（Python 3.10 + FastAPI），为 ESP32 绘图机/写字机提供云端路径生成、任务下发和设备管理能力。通过 MCP 协议与小智官方云（xiaozhi.me）集成，支持语音控制绘图/写字。

旧系统（多后端 AI 路由、Chat、Admin、Voice、Provider 探测）已在 P4/P5 瘦身中物理删除。

**公网入口：** `https://chat.donglicao.com/dlc/*`（nginx → :8081）

---

## 常用命令

常用命令速查见 `.kimi-code/AGENTS.md`。本节仅保留小程序一键上传流程：

```bash
cd esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile
npx vue-tsc --noEmit
npx uni build --platform mp-weixin
"/c/Users/zhugu/微信web开发者工具/cli.bat" upload \
  --project "$(pwd)/dist/build/mp-weixin" --v "X.Y.Z" -d "提交说明"
git add manifest.config.ts src/manifest.json src/pages.json
git commit -m "chore: bump version to X.Y.Z" && git push origin main
cd /d/QWEN3.0
git add esp32S_XYZ && git commit -m "chore: bump esp32S_XYZ submodule" && git push origin main
```

注意事项：AppID `wxbf3c1e0013b46343`；每次上传前 bump `versionName`/`versionCode`；上传后需在 [mp.weixin.qq.com](https://mp.weixin.qq.com) 提交审核。

---

## 架构

### 请求处理链路（P4/P5 瘦身后的真实架构）

```
Client → server_dlc.py (FastAPI 入口，:8081，/docs 已禁用 SEC-05)
      → dlc_api/routes.py (/dlc/tasks/* + /dlc/devices/*，verify_dlc_api_token)
      → dlc_core (handle_draw / handle_write / handle_draw_from_image)
      → dlc_core/dispatch.py → device_gateway (Redis 任务队列 + WSS 下发到 ESP32)
      → Client (JSON)
小智云 MCP → dlc_mcp/server.py (JSON-RPC stdio ↔ WS bridge，mcp_pipe.py)
          → dlc_api/routes.py (/dlc/tasks/* ...)
微信小程序 → server_dlc.py (/device/v1/app/*，device_app_router 聚合)
```

### 关键模块归属（当前在用）

| 职责 | 模块 |
|------|------|
| HTTP 入口 | `server_dlc.py` |
| DLC 路由 | `dlc_api/` (`routes.py`, `app.py`, `deps.py`, `schemas.py`, `device_app_router.py`) |
| 绘图/写字核心 | `dlc_core/` (`draw.py`, `dispatch.py`, `device_status.py`, `write.py`, `path_validator.py`, `presets.py`, `safety.py`, `intent.py`) |
| MCP JSON-RPC | `dlc_mcp/` (`server.py`, `mcp_pipe.py`) |
| 设备网关 | `device_gateway/` (Redis 队列、WS、设备状态、family approval、gallery) |
| 设备 App API | `routes/` (`device_app_api.py`, `device_app_tasks.py`, `images_backends.py`, `device_app_gallery.py`) |
| 鉴权/限流 | `access_guard.py`, `rate_limiter.py`, `rate_limiter_redis.py`, `ws_ticket.py`, `device_logic/auth.py` |
| 图生 | `dashscope_image_client.py`（DashScope/wanx，经 `asyncio.to_thread`） |

**已退役模块（禁止按此表去找代码）**：旧 `server.py`/`routing_engine*`/`router_v3`/`routing_executor`/`http_caller`/`context_pipeline`（代码上下文 v3.0 删）/`session_memory` 主路径/`observability`/`provider_probe`（仅 JDCloud 冷离线指针）/`backends_registry` —— 均已在 P4/P5 瘦身物理删除。详见 `progress.md` 与 `docs/archive/`。

### 部署拓扑

```
Internet → 阿里云 VPS 47.112.162.80 (nginx → server_dlc :8081, Redis)
                ↓ 同代码部署
         JDCloud 117.72.118.95 (备节点)
```

- 部署脚本：`scripts/deploy_unified.py`（双节点、容量感知、自动备份）
- 回滚：`/opt/dlc-drawing/backups/`

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

## Ponytail 第一原则（最高优先级）

本项目采用 [Ponytail](https://github.com/DietrichGebert/ponytail) 的「lazy senior dev」理念。**Ponytail 原则是本仓库所有 Agent 行为的第一优先级**，高于默认编码冲动、高于炫技式实现、高于"看起来努力"。

### 核心信条

1. **能偷懒就偷懒，能少写就少写**。
   - 会偷懒的 Agent 才是合格 Agent；写一堆低质量代码的 Agent 是坏 Agent。
   - 听话、有工程意识、能把复杂问题用最小变更解决的 Agent 才是好 Agent。
2. **优先从外部找高可靠实现，其次才自己写**。
   - 修改前先去 GitHub 等可靠来源搜索：是否已经存在经过生产验证的库、代码片段或官方示例？
   - 复用高可靠代码 = 降低测试风险、降低维护面、降低 bug 概率。
3. **写代码前必须过 Ponytail 决策阶梯**：
   1. 这个功能真的需要吗？（YAGNI）
   2. Python 标准库能直接做到吗？
   3. 平台/框架原生特性能直接做到吗？
   4. 已有依赖能直接做到吗？
   5. 能一行写完吗？
   6. 最后才写最小实现。
4. **ESP32 / 固件 / 小程序 / 嵌入式相关代码改动**：修改前**必须主动加载对应的 ESP32 / 嵌入式 / 小程序 skills**（`esp32`、`esp-idf-handling`、`esp-pio-handling`、`serial`、`jlink`、`openocd`、`workbench-*`、uni-app / Vue 相关 skills 等），用领域 skill 降低知识盲点与改错概率。
5. **最小变更、最小文件、最小函数**。
   - 不要借重构之名扩大改动面；不要写"为将来预留"的代码；不要引入不必要的抽象。
   - 能用一行就别用十行；能改一个文件就别改十个文件。

### 不可妥协的边界（Ponytail 也不得绕过）

- 信任边界的输入验证（`access_guard.py`、`identity_guard.py`）
- 防数据丢失的错误处理（`session_memory/` 持久化逻辑）
- 安全措施（白/黑名单、secret 保护、无静默降级）
- 测试门禁（`pytest`、`ruff check .`、`pyright`、`scripts/check_code_size.py`）
- 文档同步（`STATUS.md` / `progress.md` / `findings.md`）
- conventional commits、仅 stage 相关文件

### 简化标记

如果使用 Ponytail 建议的捷径，且该捷径有已知上限（全局锁、O(n²) 扫描、朴素启发式），用 `ponytail:` 注释说明上限和升级路径，并记入 `PONYTAIL-DEBT.md`。

---

## 代码质量规则

### 硬规则（不可违反）

1. **Ponytail 第一原则** — 见上文「Ponytail 第一原则」。任何代码变更必须先过 Ponytail 阶梯；ESP32 / 固件 / 小程序改动必须先加载对应 skills；优先复用 GitHub 高可靠代码而非自己写。
2. **禁止静默降级** — 生产路径中禁止使用 `except Exception: pass` 或 `except ImportError: pass`。至少必须 `logger.warning` 并说明原因。关键依赖（chromadb、tree-sitter）必须在启动时记录清晰警告，而非在运行时静默降级。
3. **禁止自动降级验证** — VPS 部署必须在真实 VPS 上验证，不能仅在 localhost 上验证。公网 API 必须通过真实域名和真实 token 测试。
4. **.env 合并而非覆盖** — 部署必须先备份 VPS 的 `.env`，追加新变量，绝不能用 `sftp.put` 覆盖。
5. **Telegram 通知通道已退役** — 不要重新注册 `/telegram` 路由、webhook 或出站通知。注意：Telegram Bot API 仍作为 gallery 图片存储后端使用（`integrations/telegram_bot/`，见 `routes/device_app_gallery.py`），这不是通知通道，不要误删。

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
| `docs/archive/strategic-plans-2026-06/REQUEST_PIPELINE_AUTHORITY_CN.md` | 旧 routing_engine 18 步流水线（已归档，routing_engine 已退役） |
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

## 设计第二原则

次于 Ponytail 第一原则，但高于一般编码习惯。遵循 SOLID、LoD、CRP，保持接口清晰、上下文精简、工具幂等可观测。详见 [`docs/AGENTS_DESIGN_PRINCIPLES.md`](docs/AGENTS_DESIGN_PRINCIPLES.md)。
