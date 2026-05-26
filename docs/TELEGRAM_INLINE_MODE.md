# Telegram Inline Mode (TG-10.0-3)

> **Status:** Active | **Created:** 2026-05-26  
> **Scope:** `@bot <query>` 任意聊天内即时回答（Operator 白名单）

## BotFather

1. `/mybots` → 选 bot → **Bot Settings** → **Inline Mode** → **Turn on**
2. 或发送 `/setinline` → 选 bot → **Enable**

## 行为

- 用户在任意聊天输入 `@YourBot 斐波那契数列` → 选 inline 结果 → 发送到当前聊天
- 仅 `TELEGRAM_CHAT_ID` 对应 Operator 可触发（他人收到空结果）
- 复用 `routing_engine.route`（与 `/chat` 同池，无多轮历史）
- `TELEGRAM_INLINE_ENABLED=0` 默认关

## Env

```env
TELEGRAM_INLINE_ENABLED=1
```

## 模块

| 文件 | 职责 |
|------|------|
| `telegram_inline.py` | 鉴权、限流、`answerInlineQuery` 结果构建 |
| `telegram_bot.py` | `answer_inline_query()` API 封装 |
| `routes/telegram.py` | webhook `inline_query` 分支 |

## 部署

```powershell
python scripts/deploy_telegram_inline_vps.py
python -m pytest tests/test_telegram_inline.py -q
```

## 验收

1. BotFather 开 Inline Mode  
2. VPS `TELEGRAM_INLINE_ENABLED=1`  
3. 任意聊天 `@bot 用一句话解释 Depends` → 出现 LiMa 结果 → 发送后可见回答
