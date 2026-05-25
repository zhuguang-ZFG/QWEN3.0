# OpenClaw 轻量部署（LiMa VPS 验证）

## 目标

- **仅**微信通道 `@tencent-weixin/openclaw-weixin`
- **大脑** `https://chat.donglicao.com/v1`（`LIMA_API_KEY`）
- **关闭**：heartbeat、memory、cron、hooks、MCP、浏览器/沙箱工具、Control UI 公网暴露
- **并行**现有 `lima-weixin-ilink`（管理员桥不动），验证通过后再决定是否切换

## 架构

```text
朋友/你 微信 ClawBot
    → OpenClaw Gateway (127.0.0.1:18789)
    → lima/lima-default
    → chat.donglicao.com/v1

（并行，不共用 token）
管理员 ↔ lima-weixin-ilink ↔ /channel
```

## 部署

```powershell
python D:\GIT\scripts\deploy_openclaw_light_vps.py
python D:\GIT\scripts\verify_openclaw_light_vps.py
```

配置模板：`deploy/openclaw/openclaw.light.json5`  
systemd：`deploy/openclaw/lima-openclaw.service`

环境变量（写入 VPS `/opt/lima-router/.env`）：

| 变量 | 用途 |
|------|------|
| `LIMA_API_KEY` | OpenClaw → LiMa API（须已存在） |
| `OPENCLAW_GATEWAY_TOKEN` | 部署脚本缺失时自动生成 |

## 微信扫码（验证必做）

确认网关稳定：`systemctl is-active lima-openclaw` 为 `active`，且 `ss -tlnp | grep 18789` 有监听。

SSH 到 VPS 后：

```bash
bash /opt/lima-router/scripts/openclaw_weixin_login_vps.sh
```

（或手动设置 `OPENCLAW_STATE_DIR` / `OPENCLAW_CONFIG_PATH` 后执行 `openclaw channels login --channel openclaw-weixin`。）

若反复 `activating` / `SIGKILL`：VPS 仅 1.8GB 内存，可**临时** `systemctl stop lima-weixin-ilink` 再启 `lima-openclaw`，或先在 Windows 跑 `scripts/start_openclaw_light_local.ps1` 验证配置。

朋友接入：`dmPolicy=pairing`，你执行：

```bash
openclaw pairing list openclaw-weixin
openclaw pairing approve openclaw-weixin <CODE>
```

## VPS 资源

当前 VPS 约 **1.8GB RAM**。`lima-openclaw` **不设 MemoryMax**（避免 cgroup OOM）；启动时会 `unset TELEGRAM_*`，防止 OpenClaw 自动拉起 Telegram 插件。

## 回滚

```bash
systemctl stop lima-openclaw
systemctl disable lima-openclaw
```

不影响 `lima-weixin-ilink` / `lima-router`。

## 参考

- [OpenClaw WeChat](https://docs.openclaw.ai/channels/wechat)
- [Pairing](https://docs.openclaw.ai/channels/pairing)
- `docs/HERMES_WEIXIN_ILINK.md`（Hermes **gateway 大脑**未用于生产；与 OpenClaw 是不同栈）
