# Telegram Bot 集成设计

> Updated: 2026-05-26
> Status: 已完成 ✅ | TG-GH-1 FRP Runbook 已补充

## 目标

为 LiMa 添加 Telegram Bot 人机交互层，支持：
1. **健康告警** — 后端进入 dead 状态时即时通知
2. **Worker 审批** — 任务完成后 inline keyboard 一键 approve/reject
3. **移动端对话** — 手机直接发消息走 LiMa 路由池（多轮上下文）
4. **远程运维** — /status /top /uptime /logs /restart
5. **自动巡检** — 每小时探活 + 每日摘要推送

## 架构

```
Telegram App (手机/桌面)
    ↕ HTTPS
Telegram Bot API (api.telegram.org)
    ↑ VPS 出站：FRP 隧道 → Windows clash 代理 → Telegram
    ↓ Webhook POST：Telegram → nginx → VPS:8080
LiMa Server (FastAPI)
    ├── routes/telegram.py          ← webhook + 命令分发 + 每日摘要
    ├── routes/telegram_commands.py ← 扩展命令 + 多轮对话 + 巡检
    ├── telegram_bot.py             ← 发送消息/keyboard 的核心库
    └── telegram_notify.py          ← 被 health_tracker/agent_tasks 调用
```

## 网络拓扑（关键）

VPS（国内阿里云）无法直连 Telegram API。出站路径：
```
VPS telegram_bot.py → httpx(proxy=127.0.0.1:7897)
    → FRP 隧道 (frps:7897 → frpc on Windows:7897)
    → Windows clash 代理
    → api.telegram.org
```

入站路径无 GFW 问题：
```
Telegram servers → https://chat.donglicao.com/telegram/webhook
    → nginx → LiMa Server:8080
```

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | BotFather 创建的 token | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | 接收通知的 chat ID | `5345665818` |
| `GFW_PROXY` | FRP 隧道代理（VPS→Windows clash） | `http://127.0.0.1:7897` |
| `TELEGRAM_WEBHOOK_SECRET` | webhook 验证密钥 | 随机字符串 |
| `TELEGRAM_DIGEST_HOUR` | 每日摘要推送时间（默认 9） | `9` |
| `TELEGRAM_STREAM_CHAT` | `/chat` 流式 draft（Bot API 9.3+ `sendMessageDraft`） | `1` |
| `TELEGRAM_STREAM_THROTTLE_MS` | draft 更新最小间隔 ms | `800` |

## 模块职责

### telegram_bot.py（核心库，89 行）

- `send_message(text, parse_mode, chat_id)` — 发送文本消息
- `send_approval(task_id, summary, files)` — 带 Approve/Reject 按钮
- `send_alert(level, text)` — 告警消息（🔴/🟡/🟢 前缀）
- `answer_callback(callback_query_id, text)` — 确认按钮点击
- `is_configured() / is_authorized(chat_id)` — 守卫函数

### telegram_draft_stream.py + routes/telegram_chat_stream.py（TG-10.0-1）

- `/chat` 默认走 **sendMessageDraft** 逐字预览 + 最终 **sendMessage** 持久化
- 复用 `speculative_stream_chunks`（与 HTTP SSE 同路由池）
- 工具关键词路径（天气/汇率等）仍走 `fc_caller`，不流式
- `TELEGRAM_STREAM_CHAT=0` 回退整段 `sendMessage`

### routes/telegram.py（路由 + 分发，~260 行）

- `POST /telegram/webhook` — 接收 Telegram 更新，验证 secret
- `POST /telegram/setup` — 注册 webhook URL（admin only）
- 命令分发 + 每日摘要定时任务 + 巡检启动

### routes/telegram_commands.py（扩展命令，212 行）

- 多轮对话（cmd_chat/cmd_clear）
- 编程路由（cmd_code）
- 系统监控（cmd_top/cmd_uptime）
- 后端评估（cmd_eval）
- Agent 任务（cmd_task/cmd_tasks）
- 后端巡检（probe_backends/start_probe_loop）

### telegram_notify.py（通知钩子，63 行）

被其他模块调用，fire-and-forget：
- `notify_health_change(backend, old_state, new_state)`
- `notify_task_ready(task_id, summary, changed_files)`
- `notify_error_spike(error_rate, strategy)`

## FRP 出站 Runbook（TG-GH-1）

VPS 经 FRP 使用 Windows Clash `7897` 访问 Telegram。Windows 重启后 frpc 必须自启。

| 组件 | 路径 / 端口 |
|------|-------------|
| frpc | `D:\GIT\frp\frpc.exe` + `frpc.toml` |
| 代理隧道 | VPS `127.0.0.1:7897` → Windows Clash `7897` |
| API 隧道 | local `8080` → VPS `8088` |
| 开机 | `local_router_start.bat` |
| 计划任务 | `LiMa-FRP-Tunnel` ← `scripts/install_frpc_service.ps1` |
| 巡检 | `infra/lima-health.bat`（含 frpc 重启） |

```powershell
powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\install_frpc_service.ps1
Start-ScheduledTask -TaskName LiMa-FRP-Tunnel
```

VPS cron（每 6h）：

```bash
python scripts/smoke_telegram_outbound.py --notify
```

## 集成点

| 模块 | 触发条件 | 通知内容 |
|------|----------|----------|
| `health_tracker.record_failure()` | backend 进入 dead 状态 | 后端名 + 错误类型 + 冷却时间 |
| `routes/agent_tasks.submit_result()` | status=needs_review | 任务摘要 + Approve/Reject 按钮 |
| `context_pipeline/evolution.py` | 策略切换 | 新策略 + 触发原因 |

## 安全边界

1. Webhook 验证：Telegram `X-Telegram-Bot-Api-Secret-Token` header
2. Chat ID 白名单：只响应 `TELEGRAM_CHAT_ID` 的消息
3. 命令鉴权：/next /stop 等操作命令需要 admin chat ID
4. 不在消息中暴露 API key 或后端 URL
5. /chat 对话内容不持久化到 Telegram 侧日志

## Webhook 注册

```bash
curl -X POST "https://api.telegram.org/bot${TOKEN}/setWebhook" \
  -d "url=https://chat.donglicao.com/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/status` | 后端健康概览（healthy/degraded/dead 计数） |
| `/health <name>` | 单个后端详细状态 |
| `/budget` | 今日各后端配额消耗 |
| `/top` | CPU 负载 / 内存 / 活跃连接数 |
| `/uptime` | 服务运行时长 + 启动时间 |
| `/logs [n]` | 最近 N 条日志（默认 10） |
| `/restart` | 远程重启服务（带确认按钮） |
| `/chat <msg>` | 多轮对话（保持 10 轮上下文） |
| `/clear` | 清除对话历史 |
| `/code <prompt>` | 编程专用路由（走 code_orchestrator） |
| `/eval <backend>` | 对指定后端跑编程 fixture 评估 |
| `/task <goal>` | 创建 Agent 任务 |
| `/tasks` | 查看待处理任务队列 |
| 直接发消息 | 自动走多轮 chat（无需 /chat 前缀） |

## 自动化任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 每日摘要 | 每天 9:00 | 后端存活数 + 请求量 + 挂掉的后端列表 |
| 后端巡检 | 每小时 | 随机 ping 5 个后端，新死亡的主动告警 |
| 健康告警 | 实时 | backend 进入 dead 状态时推送（限频 60s/backend） |
| 任务审批 | 实时 | Worker 提交 needs_review 时推送 Approve/Reject 按钮 |
