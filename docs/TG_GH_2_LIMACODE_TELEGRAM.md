# TG-GH-2 LiMa Code → Telegram 生命周期

Updated: 2026-05-26  
Status: **已在 deepcode-cli 实现**（submodule）

## 能力

| 事件 | 模块 |
|------|------|
| `task_started` / `task_finished` / `task_failed` | `deepcode-cli/src/lima/telegram-notifier.ts` |
| `task_needs_review` / `work_stopped` | 同上 |
| 注入点 | `command-runner.ts` → `sendLiMaTelegramEvent`（best-effort，失败不阻断 task） |

## Windows Worker 配置

在 LiMa Code 项目根（`deepcode-cli`）或环境变量：

```bash
LIMA_CODE_TELEGRAM_BOT_TOKEN=...   # Code 专用 bot（与 Server 不同）
LIMA_CODE_TELEGRAM_B2B=1
LIMA_SERVER_BOT_USERNAME=lima_router_bot   # Server bot @username，无 @
LIMA_CODE_TELEGRAM_PROXY=http://127.0.0.1:7897   # Windows 出站
# 回退：LIMA_CODE_TELEGRAM_CHAT_ID=...（B2B 未配时用）
```

验证：

```powershell
cd D:\GIT\deepcode-cli
npm test -- src/tests/lima-telegram-notifier.test.ts src/tests/lima-command-runner.test.ts
```

Doctor 会报告 Telegram 配置状态：`/lima doctor`

## 与 Server Telegram 分工

| 来源 | 通道 |
|------|------|
| LiMa Server | `telegram_notify` / webhook / digest |
| LiMa Code worker | B2B → Server bot（`LIMA_B2B`）或直连 Operator chat |
| **审批** | 始终在 Server bot → Operator（inline keyboard） |

## 验收 smoke

```powershell
cd D:\GIT
# dry-run（仅需 LIMA_CODE_TELEGRAM_BOT_TOKEN + chat/B2B 配置）
python scripts/smoke_tg_gh2_limacode_telegram_e2e.py

# 真实推送（Operator 批准）
python scripts/smoke_tg_gh2_limacode_telegram_e2e.py --send
```

或 deepcode-cli 跑任务：

```powershell
cd D:\GIT\deepcode-cli
# 需 LIMA_CODE_SERVER_URL + API key + Telegram env
npx tsx src/cli.ts lima task <task-id>
```

预期 Telegram 收到 started / needs_review 等事件（配置齐全时）。

## 相关

- 设计：`deepcode-cli/docs/lima-code-telegram-notifier-design.md`
- 计划：`docs/superpowers/plans/2026-05-26-telegram-github-maximization.md` TG-GH-2
