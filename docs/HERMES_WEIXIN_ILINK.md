# Hermes 微信 iLink 扫码（个人号 DM）

参考：[Hermes Weixin 文档](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/weixin)、[Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/)。

与 LiMa 自研路径对比：

| | iLink（Hermes，**当前生产**） | PC 微信 WCF（备选） |
|--|-----------------|---------------------|
| 登录 | 手机扫终端二维码 | 3.9.12 PC 版 + wcferry |
| 本机微信 | 不需要 | 需要 |
| 公网回调 | 不需要（长轮询） | 不需要 |
| 群聊 | 多数仅 DM 可靠 | 视协议而定 |

## 一键脚本（Windows）

```powershell
powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\hermes_weixin_ilink.ps1
```

或手动：

```powershell
pip install "hermes-agent[messaging]" aiohttp cryptography
hermes gateway setup    # 选 Weixin，扫码
hermes gateway run      # 保持运行
```

## 扫码后环境变量

`%USERPROFILE%\.hermes\.env` 至少要有（向导会自动写入 token）：

```env
WEIXIN_ACCOUNT_ID=<向导给出的 account_id>
WEIXIN_DM_POLICY=open
```

## 可选：大脑走 LiMa VPS

在 `~/.hermes/config.yaml` 增加 custom provider（示例，密钥放 `.env` 勿提交仓库）：

```yaml
custom_providers:
  - name: lima
    base_url: https://chat.donglicao.com/v1
    api_key: ${LIMA_API_KEY}
    api_mode: chat_completions
    models:
      lima-default:
        name: lima-default
        context_length: 128000
    model: lima-default
model:
  default: lima-default
  provider: lima
```

然后 `hermes model` 选 `lima` provider。

## 限制（官方说明）

- 登录身份为 **iLink 机器人**（`xxx@im.bot`），不是普通微信号脚本化。
- **不能像普通好友一样「转发名片」推荐给朋友**；需让对方 **微信扫一扫** 加好友二维码/链接。
- 生成可分享扫码页（本机，发给朋友打开后扫码）：

```powershell
python D:\GIT\scripts\weixin_share_qr.py
# 输出 data/weixin_share_qr.html
```

- 访客在微信里发 `/邀请` 或「邀请」可看到文字说明。
- **私聊 DM** 最稳；普通微信群消息常收不到。
- 会话过期 `errcode=-14` 时重新 `hermes gateway setup` 扫码。

## 与 LiMa `/channel` 的关系

- **Hermes 默认**：微信 ↔ Hermes Gateway ↔ Hermes 模型（会自报 Nous Research）。
- **LiMa 推荐（本仓库）**：微信 iLink ↔ `scripts/hermes_weixin_lima_bridge.py` ↔ VPS `/channel`（LiMa 欢迎语、`/help`、`/menu` 等）。

```powershell
powershell -ExecutionPolicy Bypass -File D:\GIT\scripts\start_weixin_lima_ilink.ps1
```

需先 `hermes_weixin_qr_login.py` 扫码；脚本会停掉 Hermes gateway、开 SSH 隧道 8080、跑 LiMa 桥。

不要与 Hermes gateway **同时**长轮询同一 iLink token。  
（GeWe/Gewechat VPS 路线已退役，见 `docs/WECHAT_CHANNEL_ILINK_ONLY.md`。）
