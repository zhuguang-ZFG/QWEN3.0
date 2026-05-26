# Telegram × GitHub 利用最大化 — 详细实施方案（当前主线）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:test-driven-development per slice;
> superpowers:verification-before-completion before closeout;
> document-first per `AGENTS.md`.
>
> **Goal:** 把 Telegram 打造成 LiMa 的 **移动 Operator 控制台**，把 GitHub 打造成 **代码事件总线 + 轻量远程触发器**；二者通过 LiMa Server 汇合，数据仍落 VPS/SQLite/git。
>
> **Status:** Active — 2026-05-26 起优先于 Provider Model Automation。
>
> **Baseline:** CQ-GH-001 已完成（webhook → Telegram）；Telegram 出站 FRP 7897 已修复。

---

## 1. 战略定位

```text
                    ┌─────────────────┐
                    │  手机 Telegram   │
                    │  看 / 批 / 问    │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   告警 & 摘要          命令 & 审批           对话 & 工具
   (被动推送)          (主动运维)            (chat/code)
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    LiMa Server (VPS)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         health_tracker  agent_tasks   routing_engine
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                    GitHub (事件源)
                    push / PR / CI / Issues
```

**不做：** Telegram 当数据库；GitHub 自动 merge；未验证模型自动进主路由。

---

## 2. 现状能力矩阵

### 2.1 Telegram（已实现）

| 能力 | 模块 | 状态 |
|------|------|------|
| Webhook 入站 + 命令 | `routes/telegram.py` | ✅ |
| 健康告警 | `telegram_notify` ← `health_tracker` | ✅ |
| Agent Approve/Reject | inline keyboard → `/agent/tasks/.../review` | ✅ |
| 移动 chat / code / voice | `routes/telegram_commands.py` | ✅ |
| 运维 /status /logs /restart | 同上 | ✅ |
| 每日摘要 + 8:30 播报 | `_digest_loop`, `daily_broadcast` | ✅ |
| 每小时后端探活 | `probe_backends` | ✅ |
| 出站 FRP 7897 | `telegram_bot._telegram_proxy_candidates` | ✅（需 frpc 常驻） |

### 2.2 GitHub（已实现）

| 能力 | 模块 | 状态 |
|------|------|------|
| push / PR / CI fail → Telegram | `routes/github_webhook.py` | ✅ CQ-GH-001 |
| Webhook 验签 + repo 白名单 | `github_webhook/verify.py` | ✅ |
| nginx `/github/` 反代 | VPS `patch_nginx_github_webhook.py` | ✅ |
| GitHub Models 推理后端 | `backends_registry.py` + `GITHUB_TOKEN` | ✅ |
| 读公开文件 | `dev_fetch_github_file` / Channel `/github` | ✅ |
| LiMa Code GitHub MCP | `deepcode-cli/docs/mcp.md` | 可选，客户端配置 |
| Submodule 治理 | `docs/LIMACODE_MANAGEMENT.md` | ✅ |

### 2.3 缺口（最大化目标）

| 缺口 | 价值 |
|------|------|
| LiMa Code worker → Telegram 进度 | 手机看 task 开始/完成/失败 |
| Telegram `/github owner/repo path` | 移动读参考源码 |
| Telegram `/device` Device Gateway | 硬件状态/告警 |
| GitHub CI fail → 可选创建 Agent task | 事件驱动编码 |
| 统一 **Operator 早报**（GitHub + health + tasks） | 一条消息掌握全局 |
| GitHub `issues` / `release` webhook | Issue 指派通知 |
| 部署/smoke 结果自动推送 | 闭环可见 |
| frpc/systemd 自启守护 | Telegram 出站可靠 |

---

## 3. 实施分片

### Phase TG-GH-1 — 可靠性基建（P0，~4h）

**目标：** Telegram 出站不再因 Windows 重启静默失效。

| Task | 文件 | 步骤 |
|------|------|------|
| 1.1 | `scripts/install_frpc_service.ps1` 或文档 | Windows 计划任务 / NSSM 自启 `frpc` + Clash 7897 |
| 1.2 | `scripts/smoke_telegram_outbound.py` | VPS cron：每 6h `getMe` + 失败 Telegram 告警（自指） |
| 1.3 | `docs/TELEGRAM_BOT_DESIGN.md` | 补充 frpc 运维 Runbook |
| 1.4 | VPS deploy | 上传 `telegram_bot.py` 若本地有未部署修复 |

**验收：**
- Windows 重启后 10min 内 VPS `curl -x http://127.0.0.1:7897 https://api.telegram.org` 可达
- smoke 脚本 exit 0

---

### Phase TG-GH-2 — LiMa Code → Telegram 生命周期（P0，~1 天）

**设计权威：** `deepcode-cli/docs/lima-code-telegram-notifier-design.md`

| Task | 仓库 | 内容 |
|------|------|------|
| 2.1 | deepcode-cli | `src/lima/telegram-notifier.ts`：config、redaction、sendMessage |
| 2.2 | deepcode-cli | `command-runner.ts` 注入 notifier |
| 2.3 | deepcode-cli | 事件：`task_started` / `finished` / `failed` / `needs_review` / `work_stopped` |
| 2.4 | 主仓 | 文档 + submodule 指针；**不**在 LiMa Code 收 Telegram 命令 |
| 2.5 | 双仓 | `npm test` + `pytest` 相关；Windows worker smoke |

**消息示例：**
```text
LiMa Code ▶ task cfcd3f2b started
Goal: fix routing test...
---
LiMa Code ✓ task cfcd3f2b needs_review (3 files)
[Tap Approve on Server bot]
```

**验收：**
- 本地 `/lima task <id>` 三条事件进 Telegram
- worker 失败不阻断 task 执行

---

### Phase TG-GH-3 — 统一 Operator 早报（P1，~6h）

**目标：** 合并现有 digest + GitHub 24h 活动 + Agent 队列。

| Task | 文件 |
|------|------|
| 3.1 | `routes/telegram_digest.py`（新，≤200 行） |
| 3.2 | 读 `health_tracker`、`budget_manager`、SQLite task 计数 |
| 3.3 | 读 `data/github_activity.json`（webhook 轻量累积，仅 summary） |
| 3.4 | `github_webhook/format.py` 写入 activity ring buffer（最近 50 条） |
| 3.5 | 9:00 一条 Telegram Markdown 消息 |

**早报模板：**
```text
LiMa Daily · 2026-05-26
Backends: 142 healthy / 3 dead
GitHub 24h: 2 push, 1 PR, 1 CI fail
Tasks: 1 needs_review, 0 running
Budget: github_gpt4o 12%
```

**验收：** 手动触发 `_send_unified_digest()` → Telegram 收到合并版

---

### Phase TG-GH-4 — Telegram 命令扩展（P1，~1 天）

| 命令 | 来源 | 实现 |
|------|------|------|
| `/github owner/repo path [ref]` | Channel Gateway | 移植 `channel_gateway/integrations.build_owner_github_handler` → `telegram_commands.cmd_github` |
| `/device status` | Device Gateway | HTTP `GET /device/v1/health` + 最近 task 摘要 |
| `/task_status <id>` | agent_tasks | 已有 API 包装 |
| `/deploy` | 可选 | 只读：最近 `progress.md` 条目或 VPS git rev（**不**远程 shell） |

**安全：** 全部走 `telegram_bot.is_authorized`；输出脱敏。

**验收：** 手机 `/github psf/requests README.md` 返回摘要

---

### Phase TG-GH-5 — GitHub 事件加深（P2，~1 天）

| 事件 | 行为 |
|------|------|
| `workflow_run` success（main） | 可选静默或每日汇总 |
| `issues` opened/labeled | Telegram 摘要 + 可选 inline「创建 task」 |
| `release` published | Telegram 通知 |
| `pull_request` merged | 摘要 + link |

| Task | 文件 |
|------|------|
| 5.1 | `github_webhook/format.py` 扩展 |
| 5.2 | `routes/github_webhook.py` 事件表 |
| 5.3 | 可选 callback `task_from_issue:<n>` → POST `/agent/tasks`（**默认 off** `GITHUB_WEBHOOK_AUTO_TASK=0`） |
| 5.4 | GitHub webhook 订阅扩展（`setup_github_webhook.py`） |

**验收：** 开 test issue → Telegram 收到；`AUTO_TASK=0` 时不创建 task

---

### Phase TG-GH-6 — 部署 / Smoke 推送（P2，~4h）

| 触发 | 消息 |
|------|------|
| `scripts/deploy_*.py` 成功 | `Deploy OK: CQ-xxx, health=...` |
| `scripts/smoke_*_public.py` | `Smoke 4/4 device gateway` |
| pytest 全绿（可选 CI） | 仅 CI fail 时推送（已有 workflow_run） |

实现：`deploy_common.notify_telegram(msg)` 薄封装 `telegram_notify`。

**验收：** 跑一次 deploy 脚本 → 手机收到

---

## 4. 文件结构（预计新增/修改）

```text
routes/
  telegram_digest.py          # TG-GH-3
  telegram_commands.py        # +cmd_github, +cmd_device
  github_webhook.py           # +issues/release, activity buffer

github_webhook/
  format.py                   # 扩展事件
  activity_buffer.py          # TG-GH-3 ring buffer

telegram_notify.py            # +notify_deploy, +notify_lima_code (server-side 可选)

scripts/
  smoke_telegram_outbound.py  # TG-GH-1
  install_frpc_service.ps1    # TG-GH-1

deepcode-cli/src/lima/
  telegram-notifier.ts        # TG-GH-2

docs/
  TELEGRAM_GITHUB_OPERATOR.md # 运维手册（closeout 写）
```

单文件 ≤300 行；新模块独立文件。

---

## 5. 优先级与顺序

```text
Week 1（立即）:
  TG-GH-1 可靠性
  TG-GH-2 LiMa Code 推送

Week 2:
  TG-GH-3 统一早报
  TG-GH-4 /github /device 命令

Week 3（可选）:
  TG-GH-5 GitHub 事件加深
  TG-GH-6 部署 smoke 推送
```

**然后**再启动 Provider Automation PA-A（发现报告可进 TG-GH-3 早报）。

---

## 6. 测试策略

| 切片 | 测试 |
|------|------|
| TG-GH-1 | 手动 + smoke 脚本 |
| TG-GH-2 | deepcode-cli unit tests |
| TG-GH-3 | `tests/test_telegram_digest.py` |
| TG-GH-4 | `tests/test_telegram_webhook.py` 扩展 |
| TG-GH-5 | `tests/test_github_webhook.py` 扩展 |
| TG-GH-6 | deploy 脚本 dry-run mock notify |

每切片 closeout：`pytest -q --ignore=active_model` + 更新 `progress.md`。

---

## 7. 风险与护栏

| 风险 | 护栏 |
|------|------|
| FRP 断 → 出站全挂 | TG-GH-1 自启 + outbound smoke |
| GitHub auto-task 误触发 | `GITHUB_WEBHOOK_AUTO_TASK=0` 默认；仅 inline 确认 |
| Telegram 泄露密钥 | 沿用 `_redact_logs` / notifier redaction |
| 消息轰炸 | CI success 默认不推；同类告警 60s 限频 |
| LiMa Code 双 token | 可复用 Server token+chat_id 或独立 env |

---

## 8. 验收总清单（主线完成定义）

- [ ] Windows 重启后 Telegram 出站自愈
- [ ] LiMa Code task 全生命周期可在手机追踪
- [ ] 每日一条合并早报（health + GitHub + tasks）
- [ ] `/github` `/device` 可在 Telegram 使用
- [ ] GitHub push/PR/CI fail 已验证（CQ-GH-001 ✅）
- [ ] 文档 `docs/TELEGRAM_GITHUB_OPERATOR.md` + `progress.md` 证据

---

## 9. 相关文档

| 文档 | 用途 |
|------|------|
| `docs/TELEGRAM_BOT_DESIGN.md` | Telegram 架构 |
| `docs/GITHUB_WEBHOOK_INTEGRATION.md` | Webhook 配置 |
| `deepcode-cli/docs/lima-code-telegram-notifier-design.md` | Worker 推送 |
| `docs/superpowers/plans/2026-05-26-provider-model-automation-full-plan.md` | **存档**，后续衔接 |
