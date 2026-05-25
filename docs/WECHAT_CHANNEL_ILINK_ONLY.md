# 微信通道（仅 iLink 本机桥）

**GeWe / Gewechat / VPS sidecar（9919+2531）已于 2026-05-25 退役并自 VPS 清理。**

## 生产架构

```text
微信用户 → iLink 长轮询（本机 Windows）
       → scripts/hermes_weixin_lima_bridge.py
       → SSH 隧道 127.0.0.1:8080
       → VPS lima-router /channel/v1/wechat/message
```

## 本机启动（需常开电脑 + SSH 隧道）

```powershell
powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\start_weixin_lima_ilink.ps1
```

## VPS 24h（推荐，不依赖本机）

```powershell
python scripts/hermes_weixin_qr_login.py   # 本机或 VPS 扫码一次
python scripts/deploy_weixin_ilink_vps.py  # 同步账户 JSON + systemd lima-weixin-ilink
```

VPS 上桥直连 `http://127.0.0.1:8080/channel`，**不需要** Hermes `gateway run`（大脑仍是 LiMa）。

扫码：`python scripts/hermes_weixin_qr_login.py`（SSH 无图形界面时会打印 URL/ASCII）

分享加好友：`python scripts/weixin_share_qr.py` → `data/weixin_share_qr.html`

## 本地验证（无真微信）

```powershell
python scripts/wechat_fake_vps_smoke.py
python -m pytest tests/test_wechat_channel_smoke.py -q
```

## VPS 清理 GeWe（已执行可重跑）

```powershell
python scripts/cleanup_gewe_vps.py
```

## 历史资料

退役脚本：`scripts/archive/gewe_retired/README.md`
