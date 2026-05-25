# 微信 iLink 桥接部署到 VPS

## 为什么放 VPS

| 本机 Windows | VPS |
|--------------|-----|
| 电脑要常开 | 24h 在线 |
| SSH 隧道 8080 | 直连 `127.0.0.1:8080` |
| 易起多个桥进程 | systemd 单实例 |
| 休眠/断网即断 | 与 `lima-router` 同机更稳 |

iLink 用 **长轮询**，VPS 无需公网回调端口（GeWe 9919 路线已退役）。

## 前提

1. 已在任意机器完成 **iLink 扫码**（`scripts/hermes_weixin_qr_login.py`）
2. VPS 已有 **lima-router** + `LIMA_WECHAT_SIDECAR_TOKEN`
3. 将 `~/.hermes/weixin/accounts/<account>.json` 同步到 VPS（含 token，勿提交 git）

## 部署

```powershell
cd D:\GIT
python scripts/deploy_weixin_ilink_vps.py
```

脚本会：上传 `hermes_weixin_lima_bridge.py`、安装依赖、写入 systemd `lima-weixin-ilink`、重启服务。

## 扫码在 VPS 上（可选）

无图形界面时用脚本输出 URL + ASCII 码，SSH 里执行：

```bash
cd /opt/lima-router
python3.10 scripts/hermes_weixin_qr_login.py
```

或本机扫码后只 **拷贝账户 JSON** 到 VPS。

## 会话过期

iLink `errcode=-14` 时需重新扫码（本机或 VPS 再跑 qr_login）。

## 注意

GeWe/Gewechat（2531/9919）已从 VPS 清理，勿再部署。见 `docs/WECHAT_CHANNEL_ILINK_ONLY.md`。
