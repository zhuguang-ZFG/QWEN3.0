# GeWe / Gewechat 路线（已退役）

**退役日期：** 2026-05-25  
**原因：** VPS 自托管 Gewechat（2531）+ LiMa sidecar（9919）依赖 GeWe 设备库，长期不可用。

**后续 iLink/WCF 也已退役**，见 `scripts/archive/wechat_retired/` 与 `docs/WECHAT_RETIRED.md`。

## 仍在用的微信入口

| 入口 | 说明 |
|------|------|
| iLink 本机桥 | `scripts/start_weixin_lima_ilink.ps1` → VPS `/channel` |
| 假 sidecar smoke | `scripts/wechat_fake_vps_smoke.py` |
| Telegram | `routes/telegram.py`（可选） |

## VPS 清理

已执行或可随时重跑：

```powershell
python scripts/cleanup_gewe_vps.py
```

会停止 `lima-wechat-sidecar`、删除 `gewe` 容器、去掉 nginx `/gewe/*`、从 `.env` 删除 `GEWECHAT_*`（**保留** `LIMA_WECHAT_SIDECAR_TOKEN` 供 iLink 桥认证）。

## 本目录内容

历史部署/排障脚本，**勿再用于生产**。仅供参考或删除。
