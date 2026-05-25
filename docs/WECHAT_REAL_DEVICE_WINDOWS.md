# 微信真机联调（Windows + WeChatFerry）

GeWeAPI 注册不了、VPS 自托管 Gewechat 又连不上官方**设备库**时，用 **本机 Windows 微信 PC 版** 最现实。

LiMa 的 `/channel` 已在 VPS 验证通过；只差「真微信消息入口」。

## 架构

```text
手机微信 <--同步-- Windows 微信 PC 版
                      ^
                      | wcferry Hook
                      v
              wcf_lima_bridge.py (本机)
                      |
              SSH 隧道 :8080
                      v
              VPS lima-router /channel/v1/wechat/message
```

GeWe 公网回调已下线；WCF 路径直连 LiMa `/channel`（经 SSH 隧道或本机 router）。

## 步骤

### 1. 安装 wcferry

```powershell
pip install wcferry
```

### 2. 安装对应版本微信 PC 客户端

本机已安装 **微信 3.9.12.51**（与 wcferry 39.5.2 配套）。安装包：`D:\GIT\data\wechat_install\WeChatSetup-3.9.12.51.exe`。  
重装：`powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\install_wechat_wcf.ps1`

用**专用小号**登录。

### 3. SSH 隧道（另开一个 PowerShell，保持运行）

```powershell
ssh -N -L 8080:127.0.0.1:8080 -i $env:USERPROFILE\.ssh\id_ed25519 root@47.112.162.80
```

### 4. 扫码登录 PC 微信

安装脚本会自动打开微信；用手机微信扫 PC 端二维码登录（建议小号）。

### 5. 启动隧道 + 桥接（一条命令）

```powershell
cd D:\GIT
powershell -ExecutionPolicy Bypass -File scripts\start_wechat_lima_bridge.ps1
```

或手动设置环境变量后：

```powershell
$env:LIMA_CHANNEL_BASE_URL = "http://127.0.0.1:8080"
$env:LIMA_WECHAT_SIDECAR_TOKEN = "<VPS .env 里的值>"
python -m wechat_bridge.wcf_lima_bridge
```

### 6. 验证

用**另一个微信号**给本机登录的号发私聊：`你好`、`/menu`、`/算 1+2`，应收到 LiMa 回复。

## 风险说明

- Hook PC 微信同样存在风控可能，请用小号、低频使用。
- 微信版本必须与 wcferry 匹配，升级微信后可能要重装对应版本。

## Gewechat（已退役）

VPS/本机 Gewechat 路线已放弃，历史脚本见 `scripts/archive/gewe_retired/`。
