# LiMa Apprise 多通道通知 smoke（雷达 §八）

> **Default off:** `LIMA_APPRISE_SMOKE=0`

[Apprise](https://github.com/caronc/apprise) 统一 80+ 通知通道（Telegram、ntfy、邮件、Slack…）。LiMa 已有 `telegram_notify` + `smoke_ntfy.py`；Apprise 作可选 **多通道旁路**。

## 安装（可选）

```powershell
pip install apprise
```

## 配置

```env
LIMA_APPRISE_SMOKE=0
LIMA_APPRISE_ENABLED=0
LIMA_OPS_ALERTS=0
# 逗号分隔，Apprise URL 语法：
LIMA_APPRISE_URLS=ntfy://your-topic@ntfy.sh,tgram://BOT_TOKEN/CHAT_ID
```

常见 URL 示例：

| 通道 | Apprise URL |
|------|-------------|
| ntfy | `ntfy://topic@ntfy.sh` 或 `ntfy://user:pass@host/topic` |
| Telegram | `tgram://BOT_TOKEN/CHAT_ID` |
| 邮件 | `mailto://user:pass@gmail.com` |

## Smoke

```powershell
$env:LIMA_APPRISE_SMOKE=1
$env:LIMA_APPRISE_URLS="ntfy://your-secret-topic@ntfy.sh"
python scripts/smoke_apprise.py
```

未安装 `apprise` 或未配置 URL 时 smoke **skip**（exit 0），不阻塞 CI。

## 代码入口

- `notify/apprise_bridge.py` — `notify(body, title=...)`
- `notify/ops_alerts.py` — `maybe_notify_oldllm_failure`（`/oldllm refresh|sync` 失败时）
- `scripts/smoke_apprise.py` — 验收脚本

`LIMA_OPS_ALERTS=1` 且 `LIMA_APPRISE_ENABLED=1` 时，Telegram `/oldllm refresh|sync` 若 upstream chat 仍 FAIL 会旁路 Apprise 告警。

MVP 不默认打开；与 Telegram 主通道并行，供 Operator 自选第二告警路。
