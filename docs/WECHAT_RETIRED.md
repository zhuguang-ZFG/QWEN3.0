# 微信通道已全部退役

**2026-05-25 决定**：LiMa 不再维护任何微信真机/机器人接入（GeWe、iLink/Hermes、OpenClaw、WCF 小号等）。

## 访客与助手请用

| 方式 | 说明 |
|------|------|
| **网页** | https://chat.donglicao.com（主推，零安装） |
| **Telegram** | 见 `routes/telegram.py`（若已配置） |

## 已退役路线（归档）

| 路线 | 归档位置 |
|------|----------|
| GeWe / Gewechat sidecar | `scripts/archive/gewe_retired/` |
| OpenClaw 微信插件 | `scripts/archive/openclaw_retired/` |
| iLink / Hermes 本机桥 + VPS `lima-weixin-ilink` | `scripts/archive/wechat_retired/` |
| PC 微信 WCF Hook | `scripts/archive/wechat_retired/` |

运维（VPS 已执行 2026-05-25）：

```bash
systemctl stop lima-weixin-ilink
systemctl disable lima-weixin-ilink
# .env: WECHAT_BRIDGE_ENABLED=0
systemctl restart lima-router   # 或由 deploy_channel_gateway.py 完成
```

## 仍保留（非微信产品）

- **`/channel` HTTP API**：通用 sidecar 契约，仅用于本地 smoke（`wechat_fake_vps_smoke` 已归档）；默认关闭。
- **`channel_gateway/`**：斜杠命令、会话、黄历等；`/邀请` 只推网页。

历史设计文档见 `docs/WECHAT_*.md`（已作废，仅作记录）。
