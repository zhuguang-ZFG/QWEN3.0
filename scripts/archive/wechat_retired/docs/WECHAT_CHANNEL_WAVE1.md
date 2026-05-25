# 微信通道第一波体验（Wave 1）

日期：2026-05-25  
状态：实现中

## 范围

| ID | 功能 | 开关 |
|----|------|------|
| W1-1 | 语音回复 TTS（入站为语音时附带语音条） | `LIMA_CHANNEL_VOICE_REPLY=1` |
| W1-2 | `/邀请` 附带扫码图 | `LIMA_CHANNEL_INVITE_QR=1`（桥在本机拉图） |
| W1-3 | 自然语言 → 工具命令 | 无开关 |
| W1-4 | TinyFish 搜索/读链 | VPS `TINYFISH_API_KEY`（已有代码路径） |

## 出站 reply 字段

```json
{
  "text": "...",
  "send_invite_qr": true,
  "voice_reply_text": "用于 TTS 的纯文本（可选）"
}
```

桥 `wechat_bridge/weixin_outbound.py` 负责发图/语音文件。

## 验证

```powershell
python -m pytest tests/test_wechat_wave1_ux.py tests/test_channel_keyword_voice_ux.py -q
python scripts/deploy_channel_gateway.py
```
