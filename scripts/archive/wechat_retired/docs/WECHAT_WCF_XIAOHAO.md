# 微信小号当 LiMa 客服（WCF 路线）

多人**加好友私聊**同一微信号，大脑走 VPS `lima-router` `/channel`（非 ClawBot/iLink 分享 bot）。

## 架构

```text
朋友微信 ──加好友──► LiMa 专用小号（PC 微信 3.9.12.51 登录）
                         │
                    wcferry Hook
                         │
              wcf_lima_bridge.py（本机 Windows，常开）
                         │
              SSH 隧道 localhost:8080
                         │
              VPS /channel/v1/wechat/message
                         │
                    LiMa 回复 ──► 小号微信发出
```

与 `lima-weixin-ilink` **并行**：管理员可继续用 iLink ClawBot；访客加**小号好友**走 WCF。

## 前置

| 项 | 要求 |
|----|------|
| 机器 | **64 位 Windows**（Win10/11），能常开 PC 微信 |
| Python | **64 位**（与 wcferry `sdk.dll` 一致） |
| 微信客户端 | **32 位** 程序 **3.9.12.51**（装在 `Program Files (x86)`，正常） |
| 安装包 | Release 里 `WeChatSetup-3.9.12.51.exe` 实为 **32 位 PE**，不是「64 位安装包」 |

**常见误解**：「系统是 32 位、安装包是 64 位」装不上。  
实际是：**纯 32 位 Windows 整机能装微信，但跑不了 wcferry**（DLL 为 64 位）。需要换 **64 位系统** 的电脑做小号桥。

若安装器提示需要 64 位系统：当前机器是 **32 位 Windows**，请改用 64 位主机，或访客走网页 `https://chat.donglicao.com`。
| 账号 | **专用小号**（勿用大号，有风控） |
| VPS | `WECHAT_BRIDGE_ENABLED=1`，`LIMA_WECHAT_SIDECAR_TOKEN` 已配置 |
| 本机 | `pip install wcferry`，SSH 密钥可连 VPS |

审计：`python scripts/check_weixin_deploy.py`

## 一次性安装（本机）

默认 **GUI 安装 + Win11 兼容启动器**（对齐 [WeChatFerry#424](https://github.com/lich0821/WeChatFerry/issues/424)）。不要用官网新版微信。

```powershell
cd D:\GIT
powershell -ExecutionPolicy Bypass -File scripts\install_wechat_wcf.ps1
```

安装向导弹出后**点完每一步**，直到出现 `WeChat.exe`。脚本会创建桌面快捷方式 **「微信-LiMa」**。

- 只用 **微信-LiMa** 登录小号，不要用绿色「微信」快捷方式。
- 用手机扫 PC 二维码登录**小号**。
- **版本过低**：多半是装了 **64 位** 3.9（`Program Files\Tencent\WeChat`）。需改 **32 位**（`Program Files (x86)\Tencent\WeChat`）：`scripts\fix_wechat_version_low.ps1`，再 `fix_wechat_login.ps1`
- 检查 Hook：`powershell -File scripts\check_wcferry.ps1`

不推荐静默安装；若必须尝试：`install_wechat_wcf.ps1 -SilentInstall`（Win11 常失败）。

## 日常启动（两条命令）

**终端 A**（保持运行，SSH 隧道）：

```powershell
ssh -N -L 8080:127.0.0.1:8080 -i $env:USERPROFILE\.ssh\id_ed25519 root@47.112.162.80
```

**终端 B**（桥接）：

```powershell
powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\start_wechat_lima_bridge.ps1
```

或合并逻辑见 `scripts\wechat_wcf_setup.ps1`。

## 验证

1. 用**另一个微信号**加小号好友，发：`你好`、`/menu`、`/算 1+2`
2. 应收到 LiMa 回复（自动 guest 绑定，无需 `/bind`）
3. VPS：`channel health` 的 `bound_users` / `recent_messages` 会增加

## 推广文案（可转发）

```text
LiMa 微信客服：请加微信 [小号微信号] 为好友，直接发消息即可。
也可浏览器打开：https://chat.donglicao.com
```

## 风险

- Hook PC 微信可能触发风控：小号、低频、勿升级微信版本。
- 本机/WCF 进程需常驻；关机则微信客服离线。
- **不要**与 iLink 桥同时 Hook 同一微信实例。

## 相关

- 详细排障：`docs/WECHAT_REAL_DEVICE_WINDOWS.md`
- iLink 管理员桥：`docs/WECHAT_CHANNEL_ILINK_ONLY.md`
