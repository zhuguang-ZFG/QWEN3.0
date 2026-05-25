# 微信通道入口（GeWe 已退役）

GeWeAPI 注册与 VPS Gewechat（2531/9919）路线**已放弃**，相关服务已从 VPS 清理。

## 当前可用入口

| 方案 | 真微信 | 说明 |
|------|--------|------|
| **iLink 本机桥（推荐）** | 是 | `scripts/start_weixin_lima_ilink.ps1` |
| **假 sidecar smoke** | 否 | `scripts/wechat_fake_vps_smoke.py` 验证 `/channel` |
| **Telegram** | 否 | 运维更简单，见 `routes/telegram.py` |
| **PC 微信 WCF（备选）** | 是 | `wechat_bridge/wcf_lima_bridge.py`，需专用小号 |

详见 [WECHAT_CHANNEL_ILINK_ONLY.md](WECHAT_CHANNEL_ILINK_ONLY.md)。

## 清理命令

```powershell
python scripts/cleanup_gewe_vps.py
```
