# Telegram Bot-to-Bot (TG-10.0-2)

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** LiMa Code bot → LiMa Server bot → Operator 手机（审批仍走 Server bot）

## 前置（BotFather）

两个 bot 均需在 **BotFather → Bot settings → Mode settings** 打开 **Bot-to-Bot Communication Mode**。

## 消息格式

```text
LIMA_B2B
{"v":1,"type":"task_needs_review","task_id":"...","summary":"...","changed_files":["a.py"]}
```

Server 回复（仅 ACK，避免循环）：

```text
LIMA_B2B_ACK
{"ok":true,"type":"task_needs_review"}
```

## Server（VPS `.env`）

```env
TELEGRAM_B2B_ENABLED=1
TELEGRAM_CODE_BOT_USERNAMES=lima_code_bot
```

## LiMa Code（Windows worker）

```env
LIMA_CODE_TELEGRAM_BOT_TOKEN=<code_bot_token>
LIMA_CODE_TELEGRAM_B2B=1
LIMA_SERVER_BOT_USERNAME=lima_router_bot
# 可选：仍保留 LIMA_CODE_TELEGRAM_CHAT_ID 作非 B2B 回退
```

## 行为

| 事件 | Server 动作 |
|------|-------------|
| `task_needs_review` | `send_approval` → Operator 手机 Approve/Reject |
| 其他 lifecycle | 推送摘要到 `TELEGRAM_CHAT_ID` |

## 部署

```powershell
python scripts/deploy_telegram_b2b_vps.py
python -m pytest tests/test_telegram_b2b.py -q
```

## 验收

1. Code worker 跑 task 至 `needs_review`
2. Operator 手机收到 **带 Approve/Reject** 卡片（不经 Code bot 直发 chat_id）
3. Code bot DM 收到 `LIMA_B2B_ACK`
