# Gitee Webhook → LiMa → Telegram

> Updated: 2026-05-26
> Status: 已实现（GI-G-2）

## 目标

接收 Gitee WebHook（push / Merge Request），格式化为 Telegram 摘要；与 GitHub 双 push 时 **SHA 去重**，避免手机收两条。

## 架构

```text
Gitee repo → WebHook
  POST https://chat.donglicao.com/gitee/webhook
  Header: X-Gitee-Token / X-Gitee-Event
       → routes/gitee_webhook.py
       → gitee_webhook/verify.py
       → gitee_webhook/dedupe.py（跳过近期 GitHub 同 SHA）
       → gitee_webhook/format.py
       → telegram_notify.notify_gitee_event()
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `GITEE_WEBHOOK_ENABLED` | 是 | `1` 启用 |
| `GITEE_WEBHOOK_SECRET` | 是 | WebHook 密码（与 Gitee UI 一致） |
| `GITEE_WEBHOOK_REPOS` | 否 | `owner/repo` 白名单，逗号分隔 |
| `GITEE_WEBHOOK_DEDUPE_GITHUB` | 否 | 默认 `1`，同 SHA 5min 内跳过 Gitee push |

## 支持事件

| 事件 | 摘要 |
|------|------|
| `push_hooks` / Push Hook | 仓库、分支、commit 数、SHA、推送者 |
| `merge_request_hooks` | MR 号、标题、分支 |
| `tag_push_hooks` | Tag 名 + SHA |

## Gitee 仓库配置

1. 仓库 → 管理 → WebHooks → 添加
2. URL: `https://chat.donglicao.com/gitee/webhook`
3. 密码: 与 VPS `GITEE_WEBHOOK_SECRET` 相同
4. 勾选: Push、Merge Request（按需 Tag Push）

## 验证

```bash
python scripts/deploy_gitee_webhook.py
python scripts/patch_nginx_gitee_webhook.py
python scripts/smoke_gitee_webhook_public.py
```

## 相关

- GitHub 对称：`docs/GITHUB_WEBHOOK_INTEGRATION.md`
- 计划：`docs/superpowers/plans/2026-05-26-gitee-maximization.md`
