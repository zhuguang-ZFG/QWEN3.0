# AGENTS.md — 完整参考（Cursor 每轮勿全量注入，日常读根目录精简版）

> 本文件为 **完整** Agent 操作指南。根目录 `AGENTS.md` 为 Cursor 优化后的短摘要；需要部署/里程碑/ECC 细节时再打开本文件或 `@docs/AGENTS_REFERENCE_CN.md`。

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
| 设备 App API | `routes/`（`device_app_*`、`device_app_voice*`） |
| 语音 ASR | `device_voice/`（DashScope / FunASR / Whisper）、`voice_app_ws_ticket.py` |
| 鉴权/限流 | `access_guard.py`, `rate_limiter.py`, `ws_ticket.py`, `device_logic/auth.py` |
| 图生 | `dashscope_image_client.py`（DashScope/wanx，经 `asyncio.to_thread`） |

**已退役模块（禁止按此表去找代码）**：旧 `server.py`/`routing_engine*`/`router_v3`/`routing_executor`/`http_caller`/`context_pipeline`（代码上下文 v3.0 删）/`session_memory` 主路径/`observability`/`provider_probe`（仅 JDCloud 冷离线指针）/`backends_registry` —— 均已在 P4/P5 瘦身物理删除。详见 `progress.md` 与 `docs/archive/`。

### 部署拓扑（2026-07-10）

```
Internet → Cloudflare → 京东云 117.72.118.95 (nginx → server_dlc :8081, Redis)
                ↓ 可选 pilot
         阿里云 47.112.162.80 (历史 pilot / 部分反代)
```

- **默认目标**：`python scripts/deploy_unified.py --target jdcloud`（`get_deploy_target()` 默认 `jdcloud`）
- 部署脚本：`scripts/deploy_unified.py`（双节点、容量感知、自动备份）
- 运行时目录：`/opt/dlc-drawing/`；回滚：`/opt/dlc-drawing/backups/`
- 语音生产验证：`LIMA_VOICE_E2E_STRICT=1 python scripts/run_voice_e2e_production.py`

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
2. **优先从外部找高可靠实现，其次才自己写**。
3. **写代码前必须过 Ponytail 决策阶梯**（YAGNI → stdlib → 框架 → 已有依赖 → 一行 → 最小实现）。
4. **ESP32 / 固件 / 小程序改动**：必须先加载对应 skills（`esp32`、`esp-idf-handling`、`esp-pio-handling`、uni-app/Vue 等）。
5. **最小变更、最小文件、最小函数**。

### 不可妥协的边界（Ponytail 也不得绕过）

- 信任边界的输入验证（`access_guard.py`、`identity_guard.py`）
- 防数据丢失的错误处理
- 安全措施（白/黑名单、secret 保护、无静默降级）
- 测试门禁（`pytest`、`ruff check .`、`pyright`、`scripts/check_code_size.py`）
- 文档同步（`STATUS.md` / `progress.md` / `findings.md`）
- conventional commits、仅 stage 相关文件

详情见 [`docs/AGENTS_PONYTAIL.md`](AGENTS_PONYTAIL.md)。

---

## 代码质量规则

### 硬规则（不可违反）

1. **Ponytail 第一原则**
2. **禁止静默降级** — 禁止 `except Exception: pass`；至少 `logger.warning`
3. **禁止自动降级验证** — VPS 必须在真实域名 + token 验证
4. **.env 合并而非覆盖** — 部署先备份 VPS `.env`，追加变量
5. **Telegram 通知通道已退役** — gallery 仍用 `integrations/telegram_bot/` 存图，勿误删

### 文档语言

文档类产物默认中文；代码标识、API 字段、路径保留英文。

### 大小约束

单文件 ≤300 行；单函数 ≤50 行。

---

## 开发流程

```
1. 设计文档（docs/*.md）用于非平凡变更
2. 本地编码 → pytest → ruff + pyright
3. VPS 部署 + 健康/冒烟（scripts/deploy_unified.py）
4. 更新 STATUS.md / progress.md / findings.md
5. git commit（conventional，仅里程碑文件）→ push origin
```

## Git 规则

- **禁止** `git add .`；禁止暂存凭证、`.env`、`.lima-data/`
- 禁止未经用户许可 force-push / reset

### 多 Agent 工作区隔离

多 CLI / A2A 舰队并行时，**同一工作目录**共享 `index`、工作区文件、`HEAD`、`stash`。叠写会导致「假 commit」、冲突标记漂移、status 行数乱跳——通常不是 hook 在改文件，而是多个 Agent 写了同一主树。

| 角色 | 路径 | 允许 |
|------|------|------|
| 集成主树 | `D:\QWEN3.0`（`main`） | 只读排查、fetch、人工 merge/发版、单会话独占写、跑测试 |
| 任务 worktree | `C:\Users\zhugu\.a2a-sandboxes\<slug>` 或项目 `.worktrees/` | Agent 改代码、commit、跑针对该树的测试 |
| 他人 stash | `git stash list` 中非本任务条目 | **禁止** `pop`/`apply` 到脏主树；需要时复制到本任务 worktree 再处理 |

**硬约定：**

1. **写代码 → 先 worktree**。示例：
   ```powershell
   $slug = "feat-xxx"
   git -C D:\QWEN3.0 worktree add -b "agent/$slug" "C:\Users\zhugu\.a2a-sandboxes\$slug" main
   # Agent cwd = sandbox；完成后 commit → PR/cherry-pick → worktree remove
   ```
2. **A2A**：`A2A_AUTO_WORKTREE=1`、`A2A_WORKTREE_REPO=D:/QWEN3.0`、`A2A_OWNS_STRICT=1`（`start-a2a-bridge.ps1` 默认；也可用 `scripts/a2a_profile.ps1 -Profile safe -Persist`）。
3. **路径租约**：并行任务声明 `owns:`；重叠时严格模式拒绝，不要靠 stash 当多任务队列。
4. **状态校验**（写后 / 宣称 commit 后）：
   ```powershell
   git rev-parse HEAD
   git cat-file -t <hash>
   git log -1 --oneline
   git status --porcelain
   ```
5. **生命周期**：任务结束删除 worktree 与对应 `a2a/*` / `agent/*` 分支；`git worktree prune` 清僵尸登记。主树看到冲突标记时先停写，再 `checkout -- <file>` 或在隔离树解决。

## 里程碑协作协议

1. 用户实现里程碑切片
2. Agent 审查 → 测试 → `git diff --check`
3. 更新 `progress.md` / `findings.md`
4. 仅 stage 相关文件 → commit → push
5. 推送后再提议下一里程碑

**自动结项**（用户未说「不要部署/提交」时）：pytest → VPS 部署 → 文档 → commit/push。

**小程序改动**：`esp32S_XYZ/.../manager-mobile/` 变更时执行一键上传（见上文常用命令）。

## ECC 开发流程

见 [`docs/ECC_WORKFLOW_CN.md`](ECC_WORKFLOW_CN.md)。ECC 低于本文件硬规则与用户直接指令。

---

## 关键文档

| 文档 | 用途 |
|------|------|
| `STATUS.md` / `docs/PROJECT_STATUS_CN.md` | 当前项目状态 |
| `docs/ARCHITECTURE.md` | 系统架构 |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 部署硬规则 |
| `docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md` | Cursor token / MCP 分档 |
| `findings.md` / `progress.md` | 证据与执行日志 |

## 环境变量

见 `.env.example`。关键：

| 变量 | 用途 |
|------|------|
| `LIMA_API_KEY` / `LIMA_ADMIN_TOKEN` | API / 管理 |
| `LIMA_DEPLOY_KEY_PATH` | VPS SSH 私钥 |
| `LIMA_VOICE_ENABLED` | 启用小程序语音（生产 `1`） |
| `LIMA_VOICE_ASR_PROVIDER` | `dashscope` / `funasr` / `whisper` |
| `DASHSCOPE_ASR_MODEL` | REST 按住说话（默认 `qwen3-asr-flash`） |
| `LIMA_VOICE_STREAM_ASR_MODEL` | WS 流式（空=缓冲模式） |
| `DASHSCOPE_API_KEY` | DashScope 凭证 |

## CodeGraph

索引：`.codegraph/codegraph.db`。**禁止** GitNexus。大改前 `codegraph sync .`；删模块前 `python scripts/codegraph_orphans.py --fanin`。

## 设计第二原则

见 [`docs/AGENTS_DESIGN_PRINCIPLES.md`](AGENTS_DESIGN_PRINCIPLES.md)。
