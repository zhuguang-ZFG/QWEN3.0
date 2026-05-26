# GitHub Webhook → LiMa → Telegram

> Updated: 2026-05-26
> Status: 已实现 ✅（CQ-GH-001，本地验证 2026-05-26）

## 目标

在 LiMa Server 接收 GitHub Webhook（push / pull_request / workflow_run），格式化为简短摘要，经现有 `telegram_notify` 推送到手机。**默认关闭**，需显式配置后才监听。

## 非目标

- 不替代 Git 托管或 LiMa 本地 SQLite。
- 不自动 `git pull`、不开 PR、不 merge（后续独立里程碑）。
- 不存储 webhook payload（仅日志 + Telegram 摘要）。

## 架构

```text
GitHub repo Settings → Webhook
  POST https://chat.donglicao.com/github/webhook
  Header: X-Hub-Signature-256
       → routes/github_webhook.py
       → github_webhook/verify.py (HMAC)
       → github_webhook/format.py (摘要)
       → telegram_notify.notify_github_event()
       → telegram_bot.send_message()
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITHUB_WEBHOOK_ENABLED` | 是 | `1` / `true` 才启用端点 |
| `GITHUB_WEBHOOK_SECRET` | 是 | GitHub Webhook secret，验签 |
| `GITHUB_WEBHOOK_REPOS` | 否 | 逗号分隔 `owner/repo` 白名单；空=全部 |

Telegram 通知依赖既有 `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`；未配置时 webhook 仍返回 200，仅写日志。

## 支持事件

| 事件 | 摘要内容 |
|------|----------|
| `push` | 仓库、分支、提交数、最新 commit 短 SHA、pusher |
| `pull_request` | action、PR 号、标题、分支 |
| `workflow_run` | action、workflow 名、结论、分支 |

其他事件：忽略，返回 `{"ok": true, "ignored": true}`。

## 安全

1. HMAC-SHA256：`X-Hub-Signature-256: sha256=<hex>`，常量时间比较。
2. 未启用或未配置 secret → **503**（不处理 body）。
3. 验签失败 → **403**。
4. 可选 repo 白名单；不在名单 → 200 + ignored（防枚举）。
5. 摘要不含密钥、不含完整 diff。

## GitHub 配置步骤

1. Repo → Settings → Webhooks → Add webhook
2. Payload URL: `https://chat.donglicao.com/github/webhook`
3. Content type: `application/json`
4. Secret: 与 `GITHUB_WEBHOOK_SECRET` 相同
5. Events: `push`, `Pull requests`, `Workflow runs`

## 验证

```powershell
pytest tests/test_github_webhook.py -q
pytest -q --ignore=active_model
python scripts/deploy_github_webhook.py
python scripts/patch_nginx_github_webhook.py   # 首次必需：nginx 需 proxy /github/
python scripts/setup_github_webhook.py
python scripts/smoke_github_webhook_public.py
```

**VPS smoke（2026-05-26）：** 公网 signed POST 200；真实 `git push` 后 GitHub `140.82.115.x` Hookshot → lima-router 200 OK。
