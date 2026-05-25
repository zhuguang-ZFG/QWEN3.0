# 微信 iLink 语音回复说明

## 平台限制

腾讯 iLink Bot 协议对**机器人出站**的 `type=VOICE` 消息存在已知限制：

- `sendmessage` 可返回 HTTP 200，日志显示发送成功
- 微信客户端**通常不显示**绿色语音气泡（通道静默丢弃）

参考：`weixin-ilink` SDK 与 `openclaw-weixin` 均改为用**文件附件**发送语音。

## LiMa 默认行为

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `LIMA_CHANNEL_VOICE_REPLY` | `0` | Channel 是否打包语音回复 |
| `LIMA_WEIXIN_VOICE_MODE` | `file` | `file`=WAV 附件；`bubble`=实验性 SILK 气泡 |
| `LIMA_WEIXIN_VOICE_FILE_CAPTION` | `语音回复` | 文件消息说明文字 |

用户发语音入站后：

1. 先收到 **「语音回复」WAV 文件**（点开播放）
2. 再收到文字回复（含识别前缀可选）

## 入站要求

- 保存每条消息的 `context_token`（`wechat_bridge/context_tokens.py`）
- 出站文件/文字均携带该 token

## 验证

```bash
journalctl -u lima-weixin-ilink -f | grep -E 'voice wav|voice file sent'
```

应看到 `voice wav ready` 与 `voice file sent ... ok=True`。
